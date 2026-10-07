"""Hesaplar ve oturumlar.

- Şifreler argon2id ile hash'lenir (argon2-cffi varsayılanları).
- Oturum anahtarı rastgele üretilir ve httpOnly çerezde taşınır; veritabanında yalnızca SHA-256 özeti durur,
  böylece veritabanı sızsa bile geçerli oturum anahtarı ele geçmez.
- Roller: firma (yalnızca kendi kurumunun kayıtları) ve yonetici (hepsi).
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.models import AuthSession, User
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


def start_session(session: Session, response: Response, user: User, settings: Settings) -> None:
    token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(days=settings.session_days)
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
    """Firma kullanıcısı için kurum id'si; yönetici için None (kısıt yok)."""
    return None if user.role == "yonetici" else user.organization_id


def ensure_visible(user: User, organization_id: int | None) -> None:
    """Kayıt kullanıcının kurumuna ait değilse 404 (var olduğunu da sızdırmamak için 403 değil)."""
    scope = org_scope(user)
    if scope is not None and organization_id != scope:
        raise HTTPException(404, "Kayıt bulunamadı")
