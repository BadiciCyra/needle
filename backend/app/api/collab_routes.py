"""İki taraflı akış: girişim hesapları, tanıştırmalar ve açık çağrılar.

Tanıştırma: firma bir eşleşmeyi kabul eder → girişime istek gider → girişim kabul ederse pilot açılır.
Girişimin doğrulanmış hesabı yoksa program yöneticisi onun adına cevap verir (dışarıda görüşüp).

Açık çağrı: havuzda uygun girişim bulunamayan ihtiyaç girişimlerin başvurusuna açılır. Başvuran girişim
zaten ilgisini bildirmiş olduğu için firmanın kabulü tanıştırmayı da tamamlar ve pilot doğrudan açılır.
"""

import re
from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api import schemas as api
from app.api.auth_routes import me_out
from app.api.deps import embedder_dep
from app.api.pilot_routes import apply_plan_defaults, log_event
from app.api.report_routes import group_phrases
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
from app.embeddings import Embedder, cosine
from app.retrieval.pgvector import to_profile
from app.schemas import StartupProfile

router = APIRouter(tags=["girişimler ve tanıştırma"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


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
    apply_plan_defaults(session, pilot)
    log_event(session, pilot, "Pilot açıldı; plan, kilometre taşları ve hedef brief'ten önerildi")
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
        source="cagri" if intro.application_id else "eslestirme" if intro.match_id else "havuz",
        firm_note=intro.firm_note,
        startup_note=intro.startup_note,
        responded_by=intro.responded_by,
        created_at=intro.created_at,
        responded_at=intro.responded_at,
        pilot_id=pilot_id,
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
    old = session.get(Startup, user.startup_id) if user.startup_id else None
    if old is not None and old.source == "girisim" and old.status == "onay_bekliyor":
        startup = old
    else:
        startup = Startup(id=f"u{uuid4().hex[:10]}", source="girisim", status="onay_bekliyor")
        session.add(startup)
    _apply_profile(startup, payload)
    startup.embedding = None
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
        startup.embedding = embedder.embed_documents([to_profile(startup).to_search_text()])[0]
    session.commit()
    return to_profile(startup)


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
        user.startup_id = None
    session.commit()


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


SIGNAL_DAYS = 120
SIGNAL_MIN_ORGS = 2


def _startup_vector(session: Session, user: User, embedder: Embedder) -> tuple[StartupProfile, list[float]]:
    if user.role != "girisim":
        raise HTTPException(403, "Öneriler girişim hesaplarına açık")
    startup = session.get(Startup, user.startup_id) if user.startup_id else None
    if startup is None:
        raise HTTPException(409, "Önerileri görmek için önce girişim profilinizi bağlayın")
    profile = to_profile(startup)
    vector = list(startup.embedding) if startup.embedding is not None else embedder.embed_query(profile.to_search_text())
    return profile, vector


def _closest(own: list[str], wanted: list[str], embedder: Embedder) -> tuple[str, str] | None:
    if not own or not wanted:
        return None
    vectors = embedder.embed_documents(own + wanted)
    mine, theirs = vectors[: len(own)], vectors[len(own):]
    score, i, j = max((cosine(a, b), i, j) for i, a in enumerate(mine) for j, b in enumerate(theirs))
    return (own[i], wanted[j]) if score > 0 else None


def _best_pair(own: list[str], wanted: list[str], embedder: Embedder) -> str | None:
    pair = _closest(own, wanted, embedder)
    return f"Sizin “{pair[0]}” yetkinliğiniz ↔ aranan “{pair[1]}”" if pair else None


@router.get("/startup-account/recommendations", response_model=api.StartupRecommendations, summary="Girişime uygun çağrılar, kurumlar ve talep sinyalleri")
def startup_recommendations(
    session: Session = Depends(get_db),
    user: User = Depends(current_user),
    embedder: Embedder = Depends(embedder_dep),
):
    profile, vector = _startup_vector(session, user, embedder)

    calls = [c for c in session.scalars(select(OpenCall).order_by(OpenCall.id.desc())) if _is_open(c)]
    call_items = []
    if calls:
        records = {c.id: session.get(BriefRecord, c.brief_id) for c in calls}
        texts = []
        for c in calls:
            caps = (records[c.id].data or {}).get("required_capabilities") or []
            texts.append("\n".join([c.title, c.summary, " ; ".join(caps)]))
        for c, v in zip(calls, embedder.embed_documents(texts)):
            record = records[c.id]
            caps = (record.data or {}).get("required_capabilities") or []
            org = record.need.organization
            call_items.append(
                api.RecommendedCall(
                    id=c.id,
                    title=c.title,
                    organization=None if c.hide_organization or org is None else org.name,
                    deadline=c.deadline,
                    required_capabilities=caps,
                    score=round(cosine(vector, v), 3),
                    reason=_best_pair(profile.capabilities, caps, embedder),
                )
            )
    call_items.sort(key=lambda r: -r.score)

    directory = list_organizations(session, user)
    org_items = []
    described = [o for o in directory if o.description or o.open_calls]
    if described:
        texts = [
            "\n".join(filter(None, [o.name, o.sector, o.description, *[c.title for c in o.open_calls]])) for o in described
        ]
        for o, v in zip(described, embedder.embed_documents(texts)):
            org_items.append(
                api.RecommendedOrganization(
                    id=o.id, name=o.name, sector=o.sector, city=o.city, open_calls=len(o.open_calls), score=round(cosine(vector, v), 3)
                )
            )
    org_items.sort(key=lambda r: -r.score)

    since = _now() - timedelta(days=SIGNAL_DAYS)
    items = []
    for record in session.scalars(
        select(BriefRecord).join(Need, BriefRecord.need_id == Need.id).where(
            BriefRecord.status == "final", Need.organization_id.is_not(None), Need.created_at >= since
        )
    ):
        for cap in (record.data or {}).get("required_capabilities") or []:
            items.append((cap, f"kurum-{record.need.organization_id}"))
    groups = [g for g in group_phrases(items, embedder) if g.needs >= SIGNAL_MIN_ORGS]
    signals = []
    if groups:
        for g, v in zip(groups, embedder.embed_documents([g.capability for g in groups])):
            signals.append(
                api.DemandSignal(capability=g.capability, organizations=g.needs, variants=g.variants, score=round(cosine(vector, v), 3))
            )
    signals.sort(key=lambda s: (-s.score, -s.organizations))

    return api.StartupRecommendations(calls=call_items[:10], organizations=org_items[:10], signals=signals[:8])


def _wanted_capabilities(session: Session, organization_id: int) -> list[str]:
    since = _now() - timedelta(days=SIGNAL_DAYS)
    seen: dict[str, str] = {}
    for record in session.scalars(
        select(BriefRecord).join(Need, BriefRecord.need_id == Need.id).where(
            BriefRecord.status == "final", Need.organization_id == organization_id, Need.created_at >= since
        ).order_by(BriefRecord.id.desc())
    ):
        for cap in (record.data or {}).get("required_capabilities") or []:
            seen.setdefault(cap.strip().casefold(), cap.strip())
    return list(seen.values())


@router.get("/organization/recommendations", response_model=api.OrganizationRecommendations, summary="Kuruma uygun girişimler")
def organization_recommendations(
    session: Session = Depends(get_db),
    user: User = Depends(current_user),
    embedder: Embedder = Depends(embedder_dep),
):
    """Kurumun tanıtımı ve son ihtiyaçlarında aranan yetkinliklere göre havuzdaki en yakın girişimler.

    Girişim tarafındaki "size uygun kurumlar" listesinin karşılığı: iki taraf aynı vektör uzayında birbirini görür.
    """
    if user.role != "firma" or user.organization_id is None:
        raise HTTPException(403, "Öneriler firma hesaplarına açık")
    org = session.get(Organization, user.organization_id)
    profile = org.profile or {}
    wanted = _wanted_capabilities(session, org.id)
    open_titles = [c.title for c in session.scalars(select(OpenCall).where(OpenCall.organization_id == org.id)) if _is_open(c)]
    text = "\n".join(filter(None, [org.sector, profile.get("description"), *open_titles, " ; ".join(wanted)]))
    if not profile.get("description") and not wanted:
        raise HTTPException(409, "Önerileri görmek için kurum tanıtımınızı yazın ya da bir ihtiyaç tamamlayın")

    vector = embedder.embed_query(text)
    distance = Startup.embedding.cosine_distance(vector).label("distance")
    rows = session.execute(
        select(Startup, distance).where(Startup.embedding.is_not(None), Startup.status == "aktif").order_by(distance).limit(10)
    ).all()
    ids = [row.Startup.id for row in rows]
    on_platform = set(session.scalars(
        select(User.startup_id).where(User.startup_id.in_(ids), User.startup_verified_at.is_not(None))
    )) if ids else set()
    applied = set(session.scalars(
        select(Application.startup_id).join(OpenCall, Application.call_id == OpenCall.id).where(
            OpenCall.organization_id == org.id, Application.startup_id.in_(ids)
        )
    )) if ids else set()

    startups = []
    for row in rows:
        st = row.Startup
        pair = _closest(st.capabilities or [], wanted, embedder)
        startups.append(
            api.RecommendedStartup(
                id=st.id,
                name=st.name,
                sector=st.sector,
                maturity=st.maturity,
                location=st.location,
                capabilities=st.capabilities or [],
                score=round(1.0 - float(row.distance), 3),
                reason=f"Aradığınız “{pair[1]}” ↔ girişimin “{pair[0]}” yetkinliği" if pair else None,
                on_platform=st.id in on_platform,
                applied=st.id in applied,
            )
        )
    return api.OrganizationRecommendations(basis=wanted[:12], startups=startups)
