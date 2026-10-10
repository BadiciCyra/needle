"""Pilot yönetimi: plan, kilometre taşları, ölçülebilir hedefler, güncelleme akışı ve kapanış değerlendirmesi.

Kurum ve girişim aynı pilotu görür. Plan, kilometre taşları, hedefler, ölçümler ve notlar iki tarafa da açıktır;
pilotun durumu ve kapanış değerlendirmesi kurumda, girişimin kendi değerlendirmesi girişimdedir. Her değişiklik
güncelleme akışına olay olarak düşer ve pilotun son hareket zamanını yeniler.
"""

import re
from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.api import schemas as api
from app.auth import current_user, ensure_visible, org_scope, startup_scope
from app.config import Settings, get_settings
from app.db.models import (
    BriefRecord,
    MetricMeasurement,
    Milestone,
    Need,
    Pilot,
    PilotActivity,
    PilotMetric,
    Startup,
    User,
)
from app.db.session import get_db
from app.retrieval.pgvector import to_profile

router = APIRouter(tags=["pilotlar"])

ROLE_LABEL = {"firma": "kurum", "girisim": "girisim", "yonetici": "yonetici"}
OWNER_LABEL = {"kurum": "kurum", "girisim": "girişim", "ortak": "ortak"}
NEXT_STEP_LABEL = {
    "satin_alma": "satın alma",
    "genisletme": "genişletme",
    "yeni_pilot": "yeni pilot",
    "bitir": "bitirme",
}
STATUS_LABEL = {"active": "aktif", "paused": "duraklatıldı", "done": "tamamlandı", "cancelled": "iptal edildi"}
RESULT_LABEL = {"evet": "evet", "kismen": "kısmen", "hayir": "hayır"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _today() -> date:
    return _now().date()


def _short(text: str, limit: int = 60) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def duration_days(timeline: str | None) -> int:
    """Brief'teki süre metninden ("3 ay", "6 hafta içinde") gün sayısı; anlaşılmazsa 90."""
    match = re.search(r"(\d+)\s*(gün|gun|hafta|ay)", (timeline or "").lower())
    if not match:
        return 90
    amount, unit = int(match.group(1)), match.group(2)
    return max(7, amount * {"gün": 1, "gun": 1, "hafta": 7, "ay": 30}[unit])


def apply_plan_defaults(session: Session, pilot: Pilot) -> None:
    """Boş plan alanlarını brief'ten doldurur: amaç, kapsam, tarihler, kilometre taşı önerisi ve ilk hedef."""
    data = (session.get(BriefRecord, pilot.brief_id).data or {}) if pilot.brief_id else {}
    days = duration_days(data.get("timeline"))
    start = pilot.start_date or (pilot.started_at.date() if pilot.started_at else _today())
    pilot.goal = pilot.goal or data.get("problem")
    pilot.scope = pilot.scope or data.get("scope")
    pilot.start_date = start
    pilot.end_date = pilot.end_date or start + timedelta(days=days)

    has_milestones = session.scalar(select(Milestone.id).where(Milestone.pilot_id == pilot.id).limit(1))
    if not has_milestones:
        plan = [
            ("Başlangıç toplantısı", 7, "ortak"),
            ("Veri ve sistem erişimi", max(14, round(days * 0.2)), "kurum"),
            ("Kurulum ve entegrasyon", round(days * 0.4), "girisim"),
            ("Ara ölçüm", round(days * 0.65), "ortak"),
            ("Son ölçüm ve değerlendirme", days, "ortak"),
        ]
        for title, offset, owner in plan:
            due = datetime.combine(start + timedelta(days=offset), time(), tzinfo=timezone.utc)
            session.add(Milestone(pilot_id=pilot.id, title=title, due_date=due, owner=owner))

    has_metric = session.scalar(select(PilotMetric.id).where(PilotMetric.pilot_id == pilot.id).limit(1))
    criteria = (data.get("success_criteria") or "").strip()
    if not has_metric and criteria:
        session.add(PilotMetric(pilot_id=pilot.id, name=criteria[:200], due_date=pilot.end_date))
    session.flush()


def log_event(session: Session, pilot: Pilot, body: str, user: User | None = None, kind: str = "olay") -> None:
    session.add(
        PilotActivity(
            pilot_id=pilot.id,
            kind=kind,
            author_role=ROLE_LABEL.get(user.role, "sistem") if user else "sistem",
            author_name=user.name if user else None,
            body=body,
        )
    )
    pilot.last_activity_at = _now()


def _milestones(session: Session, pilot: Pilot) -> list[api.MilestoneOut]:
    today = _today()
    rows = session.scalars(
        select(Milestone).where(Milestone.pilot_id == pilot.id).order_by(Milestone.due_date.nulls_last(), Milestone.id)
    ).all()
    return [
        api.MilestoneOut(
            id=m.id,
            title=m.title,
            due_date=m.due_date,
            completed_at=m.completed_at,
            owner=m.owner,
            overdue=m.completed_at is None and m.due_date is not None and m.due_date.date() < today,
        )
        for m in rows
    ]


def _metrics(session: Session, pilot: Pilot) -> list[api.MetricOut]:
    today = _today()
    return [
        api.MetricOut(
            id=m.id,
            name=m.name,
            due_date=m.due_date,
            status=m.status,
            result_note=m.result_note,
            resolved_at=m.resolved_at,
            overdue=m.status == "bekliyor" and m.due_date is not None and m.due_date < today,
        )
        for m in session.scalars(
            select(PilotMetric).where(PilotMetric.pilot_id == pilot.id).order_by(PilotMetric.due_date.nulls_last(), PilotMetric.id)
        )
    ]


def pilot_out(session: Session, pilot: Pilot, settings: Settings) -> api.PilotOut:
    record = session.get(BriefRecord, pilot.brief_id)
    milestones = _milestones(session, pilot)
    days_inactive = (_now() - pilot.last_activity_at).days
    return api.PilotOut(
        id=pilot.id,
        status=pilot.status,
        match_id=pilot.match_id,
        brief_id=record.id,
        brief_title=(record.data or {}).get("title") or record.need.raw_text[:60],
        startup=to_profile(session.get(Startup, pilot.startup_id)),
        started_at=pilot.started_at,
        last_activity_at=pilot.last_activity_at,
        days_inactive=days_inactive,
        stale=pilot.status == "active" and days_inactive >= settings.pilot_stale_days,
        outcome=pilot.outcome,
        result=pilot.result,
        organization=record.need.organization.name if record.need.organization_id else None,
        milestones=milestones,
        start_date=pilot.start_date,
        end_date=pilot.end_date,
        overdue_milestones=sum(m.overdue for m in milestones),
        next_step=pilot.next_step,
        evaluated_at=pilot.evaluated_at,
    )


def pilot_detail(session: Session, pilot: Pilot, settings: Settings) -> api.PilotDetailOut:
    activity = session.scalars(
        select(PilotActivity).where(PilotActivity.pilot_id == pilot.id).order_by(PilotActivity.id.desc())
    ).all()
    return api.PilotDetailOut(
        **pilot_out(session, pilot, settings).model_dump(),
        goal=pilot.goal,
        scope=pilot.scope,
        firm_contact=pilot.firm_contact,
        startup_contact=pilot.startup_contact,
        startup_rating=pilot.startup_rating,
        startup_feedback=pilot.startup_feedback,
        collab_rating=pilot.collab_rating,
        startup_feedback_at=pilot.startup_feedback_at,
        metrics=_metrics(session, pilot),
        activity=[
            api.ActivityOut(
                id=a.id, kind=a.kind, author_role=a.author_role, author_name=a.author_name, body=a.body, created_at=a.created_at
            )
            for a in activity
        ],
    )


def get_pilot(session: Session, pilot_id: int, user: User) -> Pilot:
    pilot = session.get(Pilot, pilot_id)
    if pilot is None:
        raise HTTPException(404, "Pilot bulunamadı")
    if user.role == "girisim":
        if pilot.startup_id != startup_scope(user):
            raise HTTPException(404, "Pilot bulunamadı")
    else:
        ensure_visible(user, session.get(BriefRecord, pilot.brief_id).need.organization_id)
    return pilot


def _require_firm_side(user: User) -> None:
    if user.role == "girisim":
        raise HTTPException(403, "Bu işlem pilotu yürüten kuruma açık")


def _milestone_pilot(session: Session, milestone_id: int, user: User) -> tuple[Milestone, Pilot]:
    milestone = session.get(Milestone, milestone_id)
    if milestone is None:
        raise HTTPException(404, "Kilometre taşı bulunamadı")
    return milestone, get_pilot(session, milestone.pilot_id, user)


def _metric_pilot(session: Session, metric_id: int, user: User) -> tuple[PilotMetric, Pilot]:
    metric = session.get(PilotMetric, metric_id)
    if metric is None:
        raise HTTPException(404, "Hedef bulunamadı")
    return metric, get_pilot(session, metric.pilot_id, user)


def _due(value: date | None) -> datetime | None:
    return datetime.combine(value, time(), tzinfo=timezone.utc) if value else None


@router.get("/pilots", response_model=list[api.PilotOut], summary="Pilotlar (hareketsizlik uyarısıyla)")
def list_pilots(
    session: Session = Depends(get_db), user: User = Depends(current_user), settings: Settings = Depends(get_settings)
):
    query = select(Pilot).order_by(Pilot.id.desc())
    if user.role == "girisim":
        query = query.where(Pilot.startup_id == startup_scope(user))
    elif (scope := org_scope(user)) is not None:
        query = (
            query.join(BriefRecord, Pilot.brief_id == BriefRecord.id)
            .join(Need, BriefRecord.need_id == Need.id)
            .where(Need.organization_id == scope)
        )
    return [pilot_out(session, p, settings) for p in session.scalars(query).all()]


@router.get("/pilots/{pilot_id}", response_model=api.PilotDetailOut, summary="Pilot ayrıntısı")
def get_pilot_detail(
    pilot_id: int,
    session: Session = Depends(get_db),
    user: User = Depends(current_user),
    settings: Settings = Depends(get_settings),
):
    return pilot_detail(session, get_pilot(session, pilot_id, user), settings)


@router.patch("/pilots/{pilot_id}", response_model=api.PilotDetailOut, summary="Pilot durumu / sonucu")
def update_pilot(
    pilot_id: int,
    payload: api.PilotUpdate,
    session: Session = Depends(get_db),
    user: User = Depends(current_user),
    settings: Settings = Depends(get_settings),
):
    pilot = get_pilot(session, pilot_id, user)
    _require_firm_side(user)
    changes = payload.model_dump(exclude_unset=True)
    if "status" in changes and changes["status"] != pilot.status:
        log_event(session, pilot, f"Durum değişti: {STATUS_LABEL[pilot.status]} → {STATUS_LABEL[changes['status']]}", user)
    for field, value in changes.items():
        setattr(pilot, field, value)
    pilot.last_activity_at = _now()
    session.commit()
    return pilot_detail(session, pilot, settings)


@router.patch("/pilots/{pilot_id}/plan", response_model=api.PilotDetailOut, summary="Pilot planını güncelle")
def update_plan(
    pilot_id: int,
    payload: api.PilotPlanIn,
    session: Session = Depends(get_db),
    user: User = Depends(current_user),
    settings: Settings = Depends(get_settings),
):
    pilot = get_pilot(session, pilot_id, user)
    changes = payload.model_dump(exclude_unset=True)
    start, end = changes.get("start_date", pilot.start_date), changes.get("end_date", pilot.end_date)
    if start and end and end < start:
        raise HTTPException(422, "Bitiş tarihi başlangıçtan önce olamaz")
    for field, value in changes.items():
        setattr(pilot, field, value.strip() if isinstance(value, str) else value)
    log_event(session, pilot, "Pilot planı güncellendi", user)
    session.commit()
    return pilot_detail(session, pilot, settings)


@router.post("/pilots/{pilot_id}/plan/defaults", response_model=api.PilotDetailOut, summary="Planı brief'ten doldur")
def fill_plan_defaults(
    pilot_id: int,
    session: Session = Depends(get_db),
    user: User = Depends(current_user),
    settings: Settings = Depends(get_settings),
):
    pilot = get_pilot(session, pilot_id, user)
    apply_plan_defaults(session, pilot)
    log_event(session, pilot, "Plan brief'ten dolduruldu", user)
    session.commit()
    return pilot_detail(session, pilot, settings)


@router.post("/pilots/{pilot_id}/milestones", response_model=api.PilotDetailOut, summary="Kilometre taşı ekle")
def add_milestone(
    pilot_id: int,
    payload: api.MilestoneIn,
    session: Session = Depends(get_db),
    user: User = Depends(current_user),
    settings: Settings = Depends(get_settings),
):
    pilot = get_pilot(session, pilot_id, user)
    session.add(Milestone(pilot_id=pilot.id, title=payload.title.strip(), due_date=_due(payload.due_date), owner=payload.owner))
    log_event(session, pilot, f"Kilometre taşı eklendi: {payload.title.strip()} ({OWNER_LABEL[payload.owner]})", user)
    session.commit()
    return pilot_detail(session, pilot, settings)


@router.patch("/milestones/{milestone_id}", response_model=api.PilotDetailOut, summary="Kilometre taşını düzenle")
def edit_milestone(
    milestone_id: int,
    payload: api.MilestoneEdit,
    session: Session = Depends(get_db),
    user: User = Depends(current_user),
    settings: Settings = Depends(get_settings),
):
    milestone, pilot = _milestone_pilot(session, milestone_id, user)
    changes = payload.model_dump(exclude_unset=True)
    if "title" in changes and changes["title"]:
        milestone.title = changes["title"].strip()
    if "due_date" in changes:
        milestone.due_date = _due(changes["due_date"])
    if changes.get("owner"):
        milestone.owner = changes["owner"]
    pilot.last_activity_at = _now()
    session.commit()
    return pilot_detail(session, pilot, settings)


@router.delete("/milestones/{milestone_id}", response_model=api.PilotDetailOut, summary="Kilometre taşını sil")
def delete_milestone(
    milestone_id: int,
    session: Session = Depends(get_db),
    user: User = Depends(current_user),
    settings: Settings = Depends(get_settings),
):
    milestone, pilot = _milestone_pilot(session, milestone_id, user)
    log_event(session, pilot, f"Kilometre taşı silindi: {milestone.title}", user)
    session.delete(milestone)
    session.commit()
    return pilot_detail(session, pilot, settings)


@router.post("/milestones/{milestone_id}/complete", response_model=api.PilotDetailOut, summary="Kilometre taşını tamamla")
def complete_milestone(
    milestone_id: int,
    session: Session = Depends(get_db),
    user: User = Depends(current_user),
    settings: Settings = Depends(get_settings),
):
    milestone, pilot = _milestone_pilot(session, milestone_id, user)
    if milestone.completed_at is None:
        milestone.completed_at = _now()
        log_event(session, pilot, f"Kilometre taşı tamamlandı: {milestone.title}", user)
    session.commit()
    return pilot_detail(session, pilot, settings)


@router.post("/milestones/{milestone_id}/reopen", response_model=api.PilotDetailOut, summary="Kilometre taşını yeniden aç")
def reopen_milestone(
    milestone_id: int,
    session: Session = Depends(get_db),
    user: User = Depends(current_user),
    settings: Settings = Depends(get_settings),
):
    milestone, pilot = _milestone_pilot(session, milestone_id, user)
    if milestone.completed_at is not None:
        milestone.completed_at = None
        log_event(session, pilot, f"Kilometre taşı yeniden açıldı: {milestone.title}", user)
    session.commit()
    return pilot_detail(session, pilot, settings)


def _due_text(value: date | None) -> str:
    return f" (son tarih {value.strftime('%d.%m.%Y')})" if value else ""


@router.post("/pilots/{pilot_id}/metrics", response_model=api.PilotDetailOut, summary="Hedef ekle")
def add_metric(
    pilot_id: int,
    payload: api.MetricIn,
    session: Session = Depends(get_db),
    user: User = Depends(current_user),
    settings: Settings = Depends(get_settings),
):
    pilot = get_pilot(session, pilot_id, user)
    session.add(PilotMetric(pilot_id=pilot.id, name=payload.name.strip(), due_date=payload.due_date))
    log_event(session, pilot, f"Hedef eklendi: {_short(payload.name)}{_due_text(payload.due_date)}", user)
    session.commit()
    return pilot_detail(session, pilot, settings)


@router.patch("/metrics/{metric_id}", response_model=api.PilotDetailOut, summary="Hedefi düzenle")
def edit_metric(
    metric_id: int,
    payload: api.MetricIn,
    session: Session = Depends(get_db),
    user: User = Depends(current_user),
    settings: Settings = Depends(get_settings),
):
    metric, pilot = _metric_pilot(session, metric_id, user)
    metric.name = payload.name.strip()
    metric.due_date = payload.due_date
    log_event(session, pilot, f"Hedef güncellendi: {_short(metric.name)}{_due_text(metric.due_date)}", user)
    session.commit()
    return pilot_detail(session, pilot, settings)


@router.post("/metrics/{metric_id}/result", response_model=api.PilotDetailOut, summary="Hedefin sonucunu işaretle")
def set_metric_result(
    metric_id: int,
    payload: api.MetricResultIn,
    session: Session = Depends(get_db),
    user: User = Depends(current_user),
    settings: Settings = Depends(get_settings),
):
    metric, pilot = _metric_pilot(session, metric_id, user)
    metric.status = payload.status
    metric.result_note = (payload.note or "").strip() or None
    metric.resolved_at = None if payload.status == "bekliyor" else _now()
    label = {"tuttu": "tuttu", "tutmadi": "tutmadı", "bekliyor": "yeniden açıldı"}[payload.status]
    log_event(session, pilot, f"Hedef {label}: {_short(metric.name)}", user)
    session.commit()
    return pilot_detail(session, pilot, settings)


@router.delete("/metrics/{metric_id}", response_model=api.PilotDetailOut, summary="Hedefi sil")
def delete_metric(
    metric_id: int,
    session: Session = Depends(get_db),
    user: User = Depends(current_user),
    settings: Settings = Depends(get_settings),
):
    metric, pilot = _metric_pilot(session, metric_id, user)
    log_event(session, pilot, f"Hedef silindi: {_short(metric.name)}", user)
    session.execute(delete(MetricMeasurement).where(MetricMeasurement.metric_id == metric.id))
    session.delete(metric)
    session.commit()
    return pilot_detail(session, pilot, settings)


@router.post("/pilots/{pilot_id}/activity", response_model=api.PilotDetailOut, summary="Not yaz")
def add_note(
    pilot_id: int,
    payload: api.ActivityIn,
    session: Session = Depends(get_db),
    user: User = Depends(current_user),
    settings: Settings = Depends(get_settings),
):
    pilot = get_pilot(session, pilot_id, user)
    log_event(session, pilot, payload.body.strip(), user, kind="not")
    session.commit()
    return pilot_detail(session, pilot, settings)


@router.post("/pilots/{pilot_id}/evaluation", response_model=api.PilotDetailOut, summary="Kapanış değerlendirmesi (kurum)")
def evaluate_pilot(
    pilot_id: int,
    payload: api.PilotEvaluationIn,
    session: Session = Depends(get_db),
    user: User = Depends(current_user),
    settings: Settings = Depends(get_settings),
):
    pilot = get_pilot(session, pilot_id, user)
    _require_firm_side(user)
    pilot.result = payload.result
    pilot.next_step = payload.next_step
    pilot.startup_rating = payload.startup_rating
    pilot.outcome = (payload.comment or "").strip() or pilot.outcome
    pilot.evaluated_at = _now()
    pilot.status = "done"
    log_event(
        session,
        pilot,
        f"Pilot değerlendirildi: işe yaradı mı {RESULT_LABEL[payload.result]}, sonraki adım "
        f"{NEXT_STEP_LABEL[payload.next_step]}, girişime {payload.startup_rating}/5",
        user,
    )
    session.commit()
    return pilot_detail(session, pilot, settings)


@router.post("/pilots/{pilot_id}/startup-feedback", response_model=api.PilotDetailOut, summary="Girişimin değerlendirmesi")
def startup_feedback(
    pilot_id: int,
    payload: api.StartupFeedbackIn,
    session: Session = Depends(get_db),
    user: User = Depends(current_user),
    settings: Settings = Depends(get_settings),
):
    if user.role != "girisim":
        raise HTTPException(403, "Bu değerlendirmeyi girişim yazar")
    pilot = get_pilot(session, pilot_id, user)
    pilot.startup_feedback = payload.feedback.strip()
    pilot.collab_rating = payload.collab_rating
    pilot.startup_feedback_at = _now()
    rating = f" (iş birliği {payload.collab_rating}/5)" if payload.collab_rating else ""
    log_event(session, pilot, f"Girişim pilotu değerlendirdi{rating}", user)
    session.commit()
    return pilot_detail(session, pilot, settings)
