"""Hesaplar ve oturumlar.

- Şifreler argon2id ile hash'lenir (argon2-cffi varsayılanları).
- Oturum anahtarı rastgele üretilir ve httpOnly çerezde taşınır; veritabanında yalnızca SHA-256 özeti durur,
  böylece veritabanı sızsa bile geçerli oturum anahtarı ele geçmez.
- Roller: firma (yalnızca kendi kurumunun kayıtları), girisim (kendisine gelen davetler, açık çağrılar ve
  kendi pilotları) ve yonetici (hepsi).
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.models import AuthSession, LoginAttempt, PasswordResetToken, User
from app.db.session import get_db

COOKIE_NAME = "needle_session"
_hasher = PasswordHasher()
# Var olmayan e-postada da aynı sürede cevap vermek için (kullanıcı varlığını süreden sızdırmamak)
_DUMMY_HASH = _hasher.hash("needle-zamanlama-esitleme")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def authenticate(session: Session, email: str, password: str) -> User | None:
    user = session.scalar(select(User).where(User.email == email.strip().lower()))
    if user is None:
        verify_password(_DUMMY_HASH, password)
        return None
    return user if verify_password(user.password_hash, password) else None


def client_ip(request: Request) -> str | None:
    """nginx'in eklediği X-Real-IP (istemcinin gönderdiğini ezer); doğrudan erişimde bağlantının adresi.

    API portu yalnızca 127.0.0.1'e açık olduğundan başlığı nginx dışında kimse yazamaz.
    """
    return request.headers.get("x-real-ip") or (request.client.host if request.client else None)


def login_blocked(session: Session, email: str, ip: str | None, settings: Settings) -> bool:
    since = datetime.now(timezone.utc) - timedelta(minutes=settings.login_window_minutes)
    session.execute(delete(LoginAttempt).where(LoginAttempt.created_at < since))
    by_email = session.scalar(select(func.count()).select_from(LoginAttempt).where(LoginAttempt.email == email))
    by_ip = (
        session.scalar(select(func.count()).select_from(LoginAttempt).where(LoginAttempt.ip == ip)) if ip else 0
    )
    return by_email >= settings.login_max_failures_per_email or by_ip >= settings.login_max_failures_per_ip


def record_failed_login(session: Session, email: str, ip: str | None) -> None:
    session.add(LoginAttempt(email=email, ip=ip))


def clear_failed_logins(session: Session, email: str) -> None:
    session.execute(delete(LoginAttempt).where(LoginAttempt.email == email))


def end_all_sessions(session: Session, user: User, keep_token: str | None = None) -> None:
    """Şifre değişince diğer cihazlardaki oturumlar düşer (çalınmış oturum da)."""
    query = delete(AuthSession).where(AuthSession.user_id == user.id)
    if keep_token:
        query = query.where(AuthSession.token_hash != _token_hash(keep_token))
    session.execute(query)


def create_reset_token(session: Session, user: User, settings: Settings) -> str:
    token = secrets.token_urlsafe(32)
    # Önceki kullanılmamış bağlantılar geçersiz olur: yalnızca son gönderilen çalışır
    session.execute(delete(PasswordResetToken).where(PasswordResetToken.user_id == user.id))
    session.add(
        PasswordResetToken(
            token_hash=_token_hash(token),
            user_id=user.id,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=settings.password_reset_minutes),
        )
    )
    return token


def consume_reset_token(session: Session, token: str) -> User | None:
    record = session.get(PasswordResetToken, _token_hash(token))
    now = datetime.now(timezone.utc)
    if record is None or record.used_at is not None or record.expires_at < now:
        return None
    record.used_at = now
    return session.get(User, record.user_id)


def start_session(session: Session, response: Response, user: User, settings: Settings) -> None:
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    expires = now + timedelta(days=settings.session_days)
    session.execute(delete(AuthSession).where(AuthSession.user_id == user.id, AuthSession.expires_at < now))
    session.add(AuthSession(token_hash=_token_hash(token), user_id=user.id, expires_at=expires))
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=settings.session_days * 86400,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        path="/",
    )


def end_session(session: Session, request: Request, response: Response) -> None:
    token = request.cookies.get(COOKIE_NAME)
    if token:
        session.execute(delete(AuthSession).where(AuthSession.token_hash == _token_hash(token)))
    response.delete_cookie(COOKIE_NAME, path="/")


def current_user(request: Request, session: Session = Depends(get_db)) -> User:
    token = request.cookies.get(COOKIE_NAME)
    if token:
        record = session.get(AuthSession, _token_hash(token))
        if record and record.expires_at > datetime.now(timezone.utc):
            user = session.get(User, record.user_id)
            if user:
                return user
    raise HTTPException(401, "Oturum açmanız gerekiyor")


def require_admin(user: User = Depends(current_user)) -> User:
    if user.role != "yonetici":
        raise HTTPException(403, "Bu işlem yalnızca program yöneticisine açık")
    return user


def org_scope(user: User) -> int | None:
    """Firma kullanıcısı için kurum id'si; yönetici için None (kısıt yok).

    Girişim hesabı kurum kayıtlarına (ihtiyaç, brief, eşleşme) hiç erişemez. Bu kontrol burada olmalı:
    girişimin organization_id'si boş olduğu için aksi halde yönetici gibi "kısıtsız" sayılırdı.
    """
    if user.role == "girisim":
        raise HTTPException(403, "Bu sayfa firma hesaplarına açık")
    return None if user.role == "yonetici" else user.organization_id


def ensure_visible(user: User, organization_id: int | None) -> None:
    """Kayıt kullanıcının kurumuna ait değilse 404 (var olduğunu da sızdırmamak için 403 değil)."""
    scope = org_scope(user)
    if scope is not None and organization_id != scope:
        raise HTTPException(404, "Kayıt bulunamadı")


def startup_scope(user: User) -> str:
    """Girişim hesabının doğrulanmış profil id'si; doğrulanmamışsa 403."""
    if user.role != "girisim":
        raise HTTPException(403, "Bu işlem girişim hesaplarına açık")
    if not user.startup_id or user.startup_verified_at is None:
        raise HTTPException(403, "Girişim profiliniz henüz doğrulanmadı")
    return user.startup_id


# Kişisel e-posta servisleri alan adı doğrulamasında kullanılmaz (herkes gmail adresi alabilir)
_FREE_MAIL = {
    "gmail.com", "googlemail.com", "hotmail.com", "outlook.com", "live.com", "yahoo.com", "yandex.com",
    "yandex.com.tr", "icloud.com", "me.com", "proton.me", "protonmail.com", "msn.com", "mail.com", "aol.com",
}


def site_domain(url: str | None) -> str | None:
    if not url:
        return None
    host = url.split("//")[-1].split("/")[0].split(":")[0].lower()
    return host.removeprefix("www.") or None


def email_matches_site(email: str, website: str | None) -> bool:
    """E-posta alan adı girişimin sitesiyle aynı (ya da alt alan adı) mı? Kişisel e-posta servisleri sayılmaz."""
    domain = email.rsplit("@", 1)[-1].lower()
    site = site_domain(website)
    if not site or domain in _FREE_MAIL:
        return False
    return domain == site or domain.endswith("." + site) or site.endswith("." + domain)
