"""Hesap uç noktaları: kayıt, giriş, çıkış, oturumdaki kullanıcı ve firma profili."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import schemas as api
from app.auth import authenticate, current_user, end_session, hash_password, start_session
from app.config import Settings, get_settings
from app.db.models import Organization, User
from app.db.session import get_db

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
    response: Response,
    session: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    user = authenticate(session, payload.email, payload.password)
    if user is None:
        # Hangisinin yanlış olduğunu söylemiyoruz (hesap varlığını sızdırmamak için)
        raise HTTPException(401, "E-posta veya şifre hatalı")
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
