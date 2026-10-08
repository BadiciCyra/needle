"""Hesap uç noktaları: kayıt, giriş, çıkış, oturumdaki kullanıcı ve firma profili."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import schemas as api
from app.auth import (
    COOKIE_NAME,
    authenticate,
    clear_failed_logins,
    client_ip,
    consume_reset_token,
    create_reset_token,
    current_user,
    end_all_sessions,
    end_session,
    hash_password,
    login_blocked,
    record_failed_login,
    start_session,
    verify_password,
)
from app.config import Settings, get_settings
from app.db.models import Organization, User
from app.db.session import get_db
from app.mailer import send_mail

router = APIRouter(prefix="/auth", tags=["hesap"])


def me_out(user: User) -> api.MeOut:
    org = user.organization
    return api.MeOut(
        id=user.id,
        name=user.name,
        email=user.email,
        role=user.role,
        organization=api.OrganizationOut(
            id=org.id, name=org.name, sector=org.sector, profile=org.profile or {}, onboarded=org.onboarded_at is not None
        )
        if org
        else None,
        startup=api.StartupAccountOut(
            id=user.startup.id,
            name=user.startup.name,
            status=user.startup.status,
            verified=user.startup_verified_at is not None,
        )
        if user.startup
        else None,
    )


@router.post("/register", response_model=api.MeOut, summary="Firma ya da girişim hesabı aç")
def register(
    payload: api.RegisterIn,
    response: Response,
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    if not payload.kvkk_onay:
        raise HTTPException(422, "Devam etmek için aydınlatma metnini onaylamanız gerekiyor")
    email = payload.email.strip().lower()
    if session.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(409, "Bu e-posta ile bir hesap zaten var")

    organization_id = None
    if payload.account_type == "firma":
        if not payload.organization_name:
            raise HTTPException(422, "Kurum adı gerekli")
        organization = Organization(name=payload.organization_name.strip(), profile={})
        session.add(organization)
        session.flush()
        organization_id = organization.id
    # Girişim hesabı burada profilsiz açılır; ardından havuzdaki profilini sahiplenir ya da yenisini açar
    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        name=payload.name.strip(),
        role=payload.account_type,
        organization_id=organization_id,
    )
    session.add(user)
    session.flush()
    start_session(session, response, user, settings)
    session.commit()
    return me_out(user)


@router.post("/login", response_model=api.MeOut, summary="Giriş yap")
def login(
    payload: api.LoginIn,
    request: Request,
    response: Response,
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    email, ip = payload.email.strip().lower(), client_ip(request)
    # Kaba kuvvet koruması: kilitliyken doğru şifre de denenmez (şifrenin doğru olduğu sızmasın)
    if login_blocked(session, email, ip, settings):
        session.commit()
        raise HTTPException(
            429, f"Çok fazla hatalı deneme. {settings.login_window_minutes} dakika sonra tekrar deneyin ya da şifrenizi sıfırlayın."
        )
    user = authenticate(session, email, payload.password)
    if user is None:
        record_failed_login(session, email, ip)
        session.commit()
        # Hangisinin yanlış olduğunu söylemiyoruz (hesap varlığını sızdırmamak için)
        raise HTTPException(401, "E-posta veya şifre hatalı")
    clear_failed_logins(session, email)
    start_session(session, response, user, settings)
    session.commit()
    return me_out(user)


@router.post("/logout", status_code=204, summary="Çıkış yap")
def logout(request: Request, response: Response, session: Session = Depends(get_db)):
    end_session(session, request, response)
    session.commit()


@router.get("/me", response_model=api.MeOut, summary="Oturumdaki kullanıcı")
def me(user: User = Depends(current_user)):
    return me_out(user)


@router.put("/profile", response_model=api.MeOut, summary="Firma profilini kaydet")
def save_profile(payload: api.OrgProfile, session: Session = Depends(get_db), user: User = Depends(current_user)):
    if user.organization is None:
        raise HTTPException(409, "Bu hesap bir kuruma bağlı değil")
    org = user.organization
    org.profile = payload.model_dump(mode="json")
    org.sector = payload.sector
    org.onboarded_at = org.onboarded_at or datetime.now(timezone.utc)
    session.commit()
    return me_out(user)


@router.post("/password-reset/request", status_code=204, summary="Şifre sıfırlama bağlantısı iste")
def request_password_reset(
    payload: api.ResetRequestIn, session: Session = Depends(get_db), settings: Settings = Depends(get_settings)
):
    # Hesap olsa da olmasa da aynı cevap: e-posta adresinin kayıtlı olup olmadığı sızmaz
    user = session.scalar(select(User).where(User.email == payload.email.strip().lower()))
    if user is None:
        return
    token = create_reset_token(session, user, settings)
    session.commit()
    link = f"{settings.app_base_url.rstrip('/')}/sifre-sifirla?anahtar={token}"
    send_mail(
        settings,
        user.email,
        "Needle şifre sıfırlama",
        f"Merhaba {user.name},\n\nŞifrenizi sıfırlamak için bağlantı ({settings.password_reset_minutes} dakika geçerli):\n"
        f"{link}\n\nBu isteği siz yapmadıysanız e-postayı yok sayın; şifreniz değişmez.",
    )


@router.post("/password-reset/confirm", status_code=204, summary="Yeni şifreyi kaydet")
def confirm_password_reset(payload: api.ResetConfirmIn, session: Session = Depends(get_db)):
    user = consume_reset_token(session, payload.token)
    if user is None:
        raise HTTPException(400, "Bağlantı geçersiz ya da süresi dolmuş. Yeni bir sıfırlama bağlantısı isteyin.")
    user.password_hash = hash_password(payload.password)
    end_all_sessions(session, user)  # açık kalmış (belki çalınmış) oturumlar düşer
    clear_failed_logins(session, user.email)
    session.commit()


@router.post("/password", status_code=204, summary="Şifre değiştir")
def change_password(
    payload: api.PasswordChangeIn,
    request: Request,
    session: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    if not verify_password(user.password_hash, payload.current_password):
        raise HTTPException(400, "Mevcut şifre hatalı")
    user.password_hash = hash_password(payload.new_password)
    end_all_sessions(session, user, keep_token=request.cookies.get(COOKIE_NAME))  # bu cihaz açık kalır
    session.commit()

