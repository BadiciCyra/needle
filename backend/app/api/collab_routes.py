"""İki taraflı akış: girişim hesapları, tanıştırmalar ve açık çağrılar.

Tanıştırma: firma bir eşleşmeyi kabul eder → girişime istek gider → girişim kabul ederse pilot açılır.
Girişimin doğrulanmış hesabı yoksa program yöneticisi onun adına cevap verir (dışarıda görüşüp).

Açık çağrı: havuzda uygun girişim bulunamayan ihtiyaç girişimlerin başvurusuna açılır. Başvuran girişim
zaten ilgisini bildirmiş olduğu için firmanın kabulü tanıştırmayı da tamamlar ve pilot doğrudan açılır.
"""

import re
from datetime import date, datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api import schemas as api
from app.api.auth_routes import me_out
from app.api.deps import embedder_dep
from app.auth import (
    current_user,
    email_matches_site,
    ensure_visible,
    org_scope,
    require_admin,
    startup_scope,
)
from app.config import Settings, get_settings
from app.db.models import (
    Application,
    BriefRecord,
    Introduction,
    Match,
    Need,
    OpenCall,
    Organization,
    Pilot,
    Startup,
    User,
)
from app.db.session import get_db
from app.embeddings import Embedder
from app.retrieval.pgvector import to_profile
from app.schemas import StartupProfile

router = APIRouter(tags=["girişimler ve tanıştırma"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------- #
# Ortak yardımcılar (routes.py de kullanır)
# --------------------------------------------------------------------------- #

def verified_owner(session: Session, startup_id: str) -> User | None:
    return session.scalar(
        select(User).where(User.startup_id == startup_id, User.startup_verified_at.is_not(None)).limit(1)
    )


def create_pilot(session: Session, intro: Introduction) -> Pilot:
    pilot = Pilot(
        brief_id=intro.brief_id, startup_id=intro.startup_id, match_id=intro.match_id, introduction_id=intro.id
    )
    session.add(pilot)
    session.flush()
    return pilot


def intro_email_draft(session: Session, intro: Introduction, sender: User, settings: Settings) -> None:
    """Hesabı olmayan girişime gidecek tanıştırma e-postasının taslağını yazar (göndermez).

    Gövde şablondan kurulur, ek LLM çağrısı yok: ihtiyacın özeti, eşleştirmenin "neden uygun" gerekçesi,
    firmanın notu ve profili sahiplenme bağlantısı. Firma ya da yönetici düzenleyip kendi e-postasından gönderir.
    """
    record = session.get(BriefRecord, intro.brief_id)
    startup = session.get(Startup, intro.startup_id)
    data = record.data or {}
    organization = record.need.organization.name if record.need.organization else "Kurumumuz"
    title = data.get("title") or record.need.raw_text[:60]
    match = session.get(Match, intro.match_id) if intro.match_id else None
    why = ((match.rationale or {}).get("fit_summary") if match else None) or ""

    lines = [
        f"Merhaba {startup.name} ekibi,",
        "",
        f"{organization} olarak “{title}” ihtiyacımız için Needle üzerinden yaptığımız eşleştirmede sizi uygun bulduk "
        "ve tanışmak istiyoruz.",
        "",
    ]
    for label, value in (
        ("İhtiyaç", data.get("problem")),
        ("Kapsam", data.get("scope")),
        ("Aranan yetkinlikler", ", ".join(data.get("required_capabilities") or [])),
        ("Başarı kriteri", data.get("success_criteria")),
        ("Süre", data.get("timeline")),
    ):
        if value:
            lines.append(f"{label}: {value}")
    if why:
        lines += ["", f"Neden sizi düşündük: {why}"]
    if intro.firm_note:
        lines += ["", intro.firm_note]
    lines += [
        "",
        "İlgilenirseniz bu e-postayı yanıtlamanız yeterli. Dilerseniz Needle'da girişim profilinizi sahiplenip "
        f"tanıştırma isteğini oradan da kabul edebilirsiniz: {settings.app_base_url.rstrip('/')}/kayit",
        "",
        "Saygılarımızla,",
        sender.name,
        organization if sender.role == "firma" else "Needle program ekibi",
    ]
    intro.email_to = startup.contact_email
    intro.email_subject = f"{organization} sizinle tanışmak istiyor: {title}"
    intro.email_body = "\n".join(lines)
    intro.email_updated_at = _now()
    intro.email_sent_at = None


def intro_out(session: Session, intro: Introduction, viewer: User | None = None) -> api.IntroductionOut:
    record = session.get(BriefRecord, intro.brief_id)
    data = record.data or {}
    pilot_id = session.scalar(select(Pilot.id).where(Pilot.introduction_id == intro.id))
    organization = record.need.organization
    return api.IntroductionOut(
        id=intro.id,
        status=intro.status,
        brief_id=intro.brief_id,
        brief=api.IntroBrief(
            title=data.get("title") or record.need.raw_text[:60],
            problem=data.get("problem"),
            scope=data.get("scope"),
            required_capabilities=data.get("required_capabilities") or [],
            success_criteria=data.get("success_criteria"),
            timeline=data.get("timeline"),
        ),
        organization=organization.name if organization else None,
        startup=to_profile(session.get(Startup, intro.startup_id)),
        startup_has_account=verified_owner(session, intro.startup_id) is not None,
        source="cagri" if intro.application_id else "eslestirme",
        firm_note=intro.firm_note,
        startup_note=intro.startup_note,
        responded_by=intro.responded_by,
        created_at=intro.created_at,
        responded_at=intro.responded_at,
        pilot_id=pilot_id,
        # Taslak firmanın iç yazışması: girişime gösterilmez
        email=api.IntroEmail(
            to=intro.email_to,
            subject=intro.email_subject,
            body=intro.email_body,
            contact_source=session.get(Startup, intro.startup_id).contact_source,
            updated_at=intro.email_updated_at,
            sent_at=intro.email_sent_at,
        )
        if intro.email_body and viewer is not None and viewer.role != "girisim"
        else None,
    )


def _brief_org(session: Session, brief_id: int) -> int | None:
    record = session.get(BriefRecord, brief_id)
    if record is None:
        raise HTTPException(404, "Kayıt bulunamadı")
    return record.need.organization_id


# --------------------------------------------------------------------------- #
# Girişim hesabı: profil sahiplenme, yeni profil, düzenleme
# --------------------------------------------------------------------------- #

def _require_startup_role(user: User) -> None:
    if user.role != "girisim":
        raise HTTPException(403, "Bu işlem girişim hesaplarına açık")


@router.post("/startup-account/claim", response_model=api.MeOut, summary="Havuzdaki profili sahiplen")
def claim_startup(
    payload: api.ClaimIn,
    session: Session = Depends(get_db),
    user: User = Depends(current_user),
    settings: Settings = Depends(get_settings),
):
    _require_startup_role(user)
    if user.startup_verified_at is not None:
        raise HTTPException(409, "Hesabınız zaten bir girişim profiline bağlı")
    startup = session.get(Startup, payload.startup_id)
    if startup is None or startup.status != "aktif":
        raise HTTPException(404, "Girişim bulunamadı")
    if verified_owner(session, startup.id):
        raise HTTPException(409, "Bu profil başka bir hesap tarafından sahiplenilmiş; program yöneticisine yazın")
    user.startup_id = startup.id
    # Varsayılan: yönetici onaylar (alan adı eşleşmesi onay listesinde ipucu olarak görünür). Anında doğrulama
    # yalnızca e-posta doğrulaması varken açılmalı (bkz. config.startup_domain_autoverify)
    autoverify = settings.startup_domain_autoverify and email_matches_site(user.email, startup.website)
    user.startup_verified_at = _now() if autoverify else None
    session.commit()
    return me_out(user)


@router.post("/startup-account/new", response_model=api.MeOut, summary="Havuzda olmayan girişim için profil aç")
def create_startup_profile(
    payload: api.StartupProfileIn, session: Session = Depends(get_db), user: User = Depends(current_user)
):
    _require_startup_role(user)
    if user.startup_verified_at is not None:
        raise HTTPException(409, "Hesabınız zaten bir girişim profiline bağlı")
    # Önceki onaylanmamış yeni profil varsa onun yerine geçer
    old = session.get(Startup, user.startup_id) if user.startup_id else None
    if old is not None and old.source == "girisim" and old.status == "onay_bekliyor":
        startup = old
    else:
        startup = Startup(id=f"u{uuid4().hex[:10]}", source="girisim", status="onay_bekliyor")
        session.add(startup)
    _apply_profile(startup, payload)
    startup.embedding = None  # yönetici onaylayınca embedding'i hesaplanıp aramaya girer
    session.flush()
    user.startup_id = startup.id
    user.startup_verified_at = None
    session.commit()
    return me_out(user)


def _apply_profile(startup: Startup, payload: api.StartupProfileIn) -> None:
    startup.name = payload.name.strip()
    startup.sector = payload.sector
    startup.maturity = payload.maturity.value
    startup.location = payload.location
    startup.website = payload.website
    startup.description = payload.description.strip()
    startup.capabilities = [c.strip() for c in payload.capabilities if c.strip()]
    startup.past_pilots = [p.strip() for p in payload.past_pilots if p.strip()]
    startup.updated_at = _now()


@router.get("/startup-account/profile", response_model=StartupProfile, summary="Kendi profilim")
def my_startup_profile(session: Session = Depends(get_db), user: User = Depends(current_user)):
    _require_startup_role(user)
    if not user.startup_id:
        raise HTTPException(404, "Hesabınız henüz bir girişim profiline bağlı değil")
    return to_profile(session.get(Startup, user.startup_id))


@router.put("/startup-account/profile", response_model=StartupProfile, summary="Profilimi güncelle")
def update_startup_profile(
    payload: api.StartupProfileIn,
    session: Session = Depends(get_db),
    user: User = Depends(current_user),
    embedder: Embedder = Depends(embedder_dep),
):
    _require_startup_role(user)
    startup = session.get(Startup, user.startup_id) if user.startup_id else None
    pending_own = startup is not None and startup.source == "girisim" and startup.status == "onay_bekliyor"
    if startup is None or (user.startup_verified_at is None and not pending_own):
        raise HTTPException(403, "Profil sahipliğiniz henüz doğrulanmadı")
    _apply_profile(startup, payload)
    if startup.status == "aktif":
        # Değişiklik eşleştirmeye hemen yansısın
        startup.embedding = embedder.embed_documents([to_profile(startup).to_search_text()])[0]
    session.commit()
    return to_profile(startup)


# --------------------------------------------------------------------------- #
# Yönetici: sahiplenme ve yeni profil onayları
# --------------------------------------------------------------------------- #

@router.get("/admin/claims", response_model=list[api.ClaimOut], summary="Onay bekleyen girişim hesapları")
def list_claims(session: Session = Depends(get_db), _: User = Depends(require_admin)):
    users = session.scalars(
        select(User)
        .where(User.role == "girisim", User.startup_id.is_not(None), User.startup_verified_at.is_(None))
        .order_by(User.created_at)
    ).all()
    out = []
    for u in users:
        startup = u.startup
        if startup.status == "reddedildi":
            continue
        out.append(
            api.ClaimOut(
                user_id=u.id,
                user_name=u.name,
                email=u.email,
                startup=to_profile(startup),
                startup_status=startup.status,
                kind="yeni_profil" if startup.status == "onay_bekliyor" else "sahiplenme",
                domain_match=email_matches_site(u.email, startup.website),
                created_at=u.created_at,
            )
        )
    return out


def _pending_claim(session: Session, user_id: int) -> User:
    user = session.get(User, user_id)
    if user is None or user.role != "girisim" or not user.startup_id or user.startup_verified_at is not None:
        raise HTTPException(404, "Onay bekleyen istek bulunamadı")
    return user


@router.post("/admin/claims/{user_id}/approve", status_code=204, summary="Girişim hesabını onayla")
def approve_claim(
    user_id: int,
    session: Session = Depends(get_db),
    _: User = Depends(require_admin),
    embedder: Embedder = Depends(embedder_dep),
):
    user = _pending_claim(session, user_id)
    startup = user.startup
    if startup.status == "aktif" and verified_owner(session, startup.id):
        raise HTTPException(409, "Bu profilin zaten doğrulanmış bir sahibi var")
    if startup.status == "onay_bekliyor":
        startup.status = "aktif"
        startup.embedding = embedder.embed_documents([to_profile(startup).to_search_text()])[0]
    user.startup_verified_at = _now()
    session.commit()


@router.post("/admin/claims/{user_id}/reject", status_code=204, summary="Girişim hesabını reddet")
def reject_claim(user_id: int, session: Session = Depends(get_db), _: User = Depends(require_admin)):
    user = _pending_claim(session, user_id)
    if user.startup.status == "onay_bekliyor":
        user.startup.status = "reddedildi"
    else:
        user.startup_id = None  # sahiplenme reddi: hesap başka bir profili deneyebilir
    session.commit()


# --------------------------------------------------------------------------- #
# Tanıştırmalar
# --------------------------------------------------------------------------- #

@router.get("/introductions", response_model=list[api.IntroductionOut], summary="Tanıştırmalar (en yeni önce)")
def list_introductions(session: Session = Depends(get_db), user: User = Depends(current_user)):
    query = select(Introduction).order_by(Introduction.id.desc())
    if user.role == "girisim":
        query = query.where(Introduction.startup_id == startup_scope(user))
    elif (scope := org_scope(user)) is not None:
        query = (
            query.join(BriefRecord, Introduction.brief_id == BriefRecord.id)
            .join(Need, BriefRecord.need_id == Need.id)
            .where(Need.organization_id == scope)
        )
    return [intro_out(session, i, user) for i in session.scalars(query).all()]


@router.post("/introductions/{intro_id}/respond", response_model=api.IntroductionOut, summary="Tanıştırmaya cevap ver")
def respond_introduction(
    intro_id: int, payload: api.IntroResponseIn, session: Session = Depends(get_db), user: User = Depends(current_user)
):
    intro = session.get(Introduction, intro_id)
    if intro is None:
        raise HTTPException(404, "Tanıştırma bulunamadı")
    if user.role == "girisim":
        if intro.startup_id != startup_scope(user):
            raise HTTPException(404, "Tanıştırma bulunamadı")
    elif user.role != "yonetici":
        raise HTTPException(403, "Tanıştırmaya girişim ya da program yöneticisi cevap verir")
    if intro.status != "bekliyor":
        raise HTTPException(409, "Bu tanıştırma zaten cevaplanmış")

    intro.status = payload.decision
    intro.startup_note = payload.note
    intro.responded_by = user.role
    intro.responded_at = _now()
    if payload.decision == "kabul":
        create_pilot(session, intro)
    session.commit()
    return intro_out(session, intro, user)


def _editable_intro(session: Session, intro_id: int, user: User) -> Introduction:
    """E-posta taslağını yalnızca isteği yapan firma ve yönetici görür ve değiştirir."""
    intro = session.get(Introduction, intro_id)
    if intro is None or user.role == "girisim":
        raise HTTPException(404, "Tanıştırma bulunamadı")
    ensure_visible(user, _brief_org(session, intro.brief_id))
    return intro


@router.post("/introductions/{intro_id}/email/draft", response_model=api.IntroductionOut, summary="E-posta taslağı oluştur")
def create_intro_email(
    intro_id: int,
    session: Session = Depends(get_db),
    user: User = Depends(current_user),
    settings: Settings = Depends(get_settings),
):
    intro = _editable_intro(session, intro_id, user)
    if intro.email_sent_at:
        raise HTTPException(409, "Bu e-posta gönderildi olarak işaretli")
    intro_email_draft(session, intro, user, settings)
    session.commit()
    return intro_out(session, intro, user)


@router.put("/introductions/{intro_id}/email", response_model=api.IntroductionOut, summary="E-posta taslağını kaydet")
def save_intro_email(
    intro_id: int, payload: api.IntroEmailIn, session: Session = Depends(get_db), user: User = Depends(current_user)
):
    intro = _editable_intro(session, intro_id, user)
    if intro.email_sent_at:
        raise HTTPException(409, "Bu e-posta gönderildi olarak işaretli; düzenlemek için işareti kaldırın")
    to = (payload.to or "").strip() or None
    if to and not re.fullmatch(api.EMAIL_PATTERN, to):
        raise HTTPException(422, "Alıcı e-posta adresi geçersiz")
    intro.email_to, intro.email_subject, intro.email_body = to, payload.subject.strip(), payload.body.strip()
    intro.email_updated_at = _now()
    session.commit()
    return intro_out(session, intro, user)


@router.post("/introductions/{intro_id}/email/sent", response_model=api.IntroductionOut, summary="Gönderildi olarak işaretle")
def mark_intro_email_sent(
    intro_id: int, payload: api.IntroEmailSentIn, session: Session = Depends(get_db), user: User = Depends(current_user)
):
    intro = _editable_intro(session, intro_id, user)
    if not intro.email_body:
        raise HTTPException(409, "Önce bir e-posta taslağı oluşturun")
    intro.email_sent_at = _now() if payload.sent else None
    session.commit()
    return intro_out(session, intro, user)


# --------------------------------------------------------------------------- #
# Açık çağrılar ve başvurular
# --------------------------------------------------------------------------- #

def _application_out(session: Session, app_: Application) -> api.ApplicationOut:
    intro_id = session.scalar(select(Introduction.id).where(Introduction.application_id == app_.id))
    pilot_id = session.scalar(select(Pilot.id).where(Pilot.introduction_id == intro_id)) if intro_id else None
    return api.ApplicationOut(
        id=app_.id,
        call_id=app_.call_id,
        startup=to_profile(session.get(Startup, app_.startup_id)),
        note=app_.note,
        status=app_.status,
        decision_note=app_.decision_note,
        created_at=app_.created_at,
        pilot_id=pilot_id,
    )


def _call_out(session: Session, call: OpenCall, user: User, detail: bool = False) -> api.OpenCallOut:
    record = session.get(BriefRecord, call.brief_id)
    data = record.data or {}
    organization = record.need.organization
    is_startup = user.role == "girisim"
    count = session.scalar(select(func.count()).select_from(Application).where(Application.call_id == call.id))
    out = api.OpenCallOut(
        id=call.id,
        brief_id=call.brief_id,
        title=call.title,
        summary=call.summary,
        organization=None if (is_startup and call.hide_organization) or organization is None else organization.name,
        sector=data.get("sector"),
        required_capabilities=data.get("required_capabilities") or [],
        deadline=call.deadline,
        status=call.status,
        created_at=call.created_at,
        hide_organization=call.hide_organization,
        application_count=0 if is_startup else count,
    )
    if is_startup and user.startup_id:
        mine = session.scalar(
            select(Application).where(Application.call_id == call.id, Application.startup_id == user.startup_id)
        )
        out.my_application = _application_out(session, mine) if mine else None
    elif detail:
        apps = session.scalars(select(Application).where(Application.call_id == call.id).order_by(Application.id)).all()
        out.applications = [_application_out(session, a) for a in apps]
    return out


def _is_open(call: OpenCall) -> bool:
    return call.status == "acik" and (call.deadline is None or call.deadline >= date.today())


def _get_call(session: Session, call_id: int, user: User) -> OpenCall:
    call = session.get(OpenCall, call_id)
    if call is None:
        raise HTTPException(404, "Çağrı bulunamadı")
    if user.role == "girisim":
        applied = user.startup_id and session.scalar(
            select(Application.id).where(Application.call_id == call.id, Application.startup_id == user.startup_id)
        )
        if not _is_open(call) and not applied:
            raise HTTPException(404, "Çağrı bulunamadı")
    else:
        ensure_visible(user, call.organization_id)
    return call


@router.post("/calls", response_model=api.OpenCallOut, summary="İhtiyacı açık çağrıya çevir")
def create_call(payload: api.OpenCallIn, session: Session = Depends(get_db), user: User = Depends(current_user)):
    record = session.get(BriefRecord, payload.brief_id)
    if record is None:
        raise HTTPException(404, "Brief bulunamadı")
    ensure_visible(user, record.need.organization_id)
    if record.status != "final":
        raise HTTPException(409, "Önce brief'i tamamlayın")
    if session.scalar(select(OpenCall.id).where(OpenCall.brief_id == record.id)):
        raise HTTPException(409, "Bu ihtiyaç için zaten bir çağrı var")
    call = OpenCall(
        brief_id=record.id,
        organization_id=record.need.organization_id,
        title=payload.title.strip(),
        summary=payload.summary.strip(),
        hide_organization=payload.hide_organization,
        deadline=payload.deadline,
    )
    session.add(call)
    session.commit()
    return _call_out(session, call, user, detail=True)


@router.get("/calls", response_model=list[api.OpenCallOut], summary="Açık çağrılar")
def list_calls(session: Session = Depends(get_db), user: User = Depends(current_user)):
    query = select(OpenCall).order_by(OpenCall.id.desc())
    if user.role == "girisim":
        calls = [c for c in session.scalars(query).all() if _is_open(c) or _applied(session, c, user)]
    else:
        if (scope := org_scope(user)) is not None:
            query = query.where(OpenCall.organization_id == scope)
        calls = session.scalars(query).all()
    return [_call_out(session, c, user) for c in calls]


def _applied(session: Session, call: OpenCall, user: User) -> bool:
    return bool(
        user.startup_id
        and session.scalar(
            select(Application.id).where(Application.call_id == call.id, Application.startup_id == user.startup_id)
        )
    )


@router.get("/calls/{call_id}", response_model=api.OpenCallOut, summary="Çağrı ayrıntısı ve başvurular")
def get_call(call_id: int, session: Session = Depends(get_db), user: User = Depends(current_user)):
    return _call_out(session, _get_call(session, call_id, user), user, detail=True)


@router.patch("/calls/{call_id}", response_model=api.OpenCallOut, summary="Çağrıyı kapat / yeniden aç")
def update_call(
    call_id: int, payload: api.OpenCallUpdate, session: Session = Depends(get_db), user: User = Depends(current_user)
):
    if user.role == "girisim":
        raise HTTPException(403, "Bu işlem çağrıyı açan kuruma açık")
    call = _get_call(session, call_id, user)
    call.status = payload.status
    session.commit()
    return _call_out(session, call, user, detail=True)


@router.post("/calls/{call_id}/applications", response_model=api.OpenCallOut, summary="Çağrıya başvur")
def apply_to_call(
    call_id: int, payload: api.ApplicationIn, session: Session = Depends(get_db), user: User = Depends(current_user)
):
    startup_id = startup_scope(user)
    call = _get_call(session, call_id, user)
    if not _is_open(call):
        raise HTTPException(409, "Bu çağrı başvuruya kapalı")
    if _applied(session, call, user):
        raise HTTPException(409, "Bu çağrıya zaten başvurdunuz")
    if session.scalar(
        select(Introduction.id).where(Introduction.brief_id == call.brief_id, Introduction.startup_id == startup_id)
    ):
        raise HTTPException(409, "Bu ihtiyaç için kurumla zaten tanıştırıldınız; Tanıştırmalar sayfasına bakın")
    session.add(Application(call_id=call.id, startup_id=startup_id, note=payload.note.strip()))
    session.commit()
    return _call_out(session, call, user, detail=True)


@router.post("/applications/{application_id}/decision", response_model=api.OpenCallOut, summary="Başvuruyu değerlendir")
def decide_application(
    application_id: int,
    payload: api.ApplicationDecisionIn,
    session: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    app_ = session.get(Application, application_id)
    if app_ is None:
        raise HTTPException(404, "Başvuru bulunamadı")
    if user.role == "girisim":
        raise HTTPException(403, "Başvuruyu çağrıyı açan kurum değerlendirir")
    call = _get_call(session, app_.call_id, user)
    if app_.status != "yeni":
        raise HTTPException(409, "Bu başvuru zaten değerlendirilmiş")

    app_.status = payload.decision
    app_.decision_note = payload.note
    app_.decided_at = _now()
    if payload.decision == "kabul":
        # Girişim başvurarak ilgisini zaten bildirdi: tanıştırma kabul edilmiş sayılır ve pilot açılır
        intro = Introduction(
            brief_id=call.brief_id,
            startup_id=app_.startup_id,
            application_id=app_.id,
            status="kabul",
            firm_note=payload.note,
            startup_note=app_.note,
            responded_by="girisim",
            responded_at=app_.created_at,
        )
        session.add(intro)
        session.flush()
        create_pilot(session, intro)
    session.commit()
    return _call_out(session, call, user, detail=True)


def call_id_for_brief(session: Session, brief_id: int) -> int | None:
    return session.scalar(select(OpenCall.id).where(OpenCall.brief_id == brief_id))


# --------------------------------------------------------------------------- #
# Kurumlar dizini
# --------------------------------------------------------------------------- #

@router.get("/organizations", response_model=list[api.OrganizationCard], summary="Kurumlar dizini")
def list_organizations(session: Session = Depends(get_db), user: User = Depends(current_user)):
    """Profilini tamamlamış ve dizinde görünmeyi kapatmamış kurumlar.

    Girişim hesabı doğrulanmadan da görebilir: talep tarafını tanımak, profil sahiplenmekten önce gelebilir.
    Gösterilen yalnızca kurumun kendi yazdığı tanıtım ve kurum adını gizlemeyen açık çağrılar; ihtiyaçlar,
    eşleştirme ayarları (sistemler, bütçe, veri kısıtları) ve kurum adını gizleyen çağrılar görünmez.
    """
    organizations = session.scalars(
        select(Organization).where(Organization.onboarded_at.is_not(None)).order_by(Organization.name)
    ).all()
    calls: dict[int, list[api.DirectoryCall]] = {}
    for call in session.scalars(
        select(OpenCall).where(OpenCall.hide_organization.is_(False)).order_by(OpenCall.id.desc())
    ):
        if _is_open(call) and call.organization_id is not None:
            calls.setdefault(call.organization_id, []).append(
                api.DirectoryCall(id=call.id, title=call.title, deadline=call.deadline)
            )
    out = []
    for org in organizations:
        profile = org.profile or {}
        if profile.get("directory_visible") is False:
            continue
        out.append(
            api.OrganizationCard(
                id=org.id,
                name=org.name,
                sector=org.sector,
                city=profile.get("city"),
                employee_range=profile.get("employee_range"),
                description=profile.get("description"),
                website=profile.get("website"),
                open_calls=calls.get(org.id, []),
                joined_at=org.onboarded_at,
            )
        )
    return out

