"""Pilot yönetimi: plan, kilometre taşları, ölçülebilir hedefler, güncelleme akışı ve kapanış değerlendirmesi.

Kurum ve girişim aynı pilotu görür. Plan, kilometre taşları, hedefler, ölçümler ve notlar iki tarafa da açıktır;
pilotun durumu ve kapanış değerlendirmesi kurumda, girişimin kendi değerlendirmesi girişimdedir. Her değişiklik
güncelleme akışına olay olarak düşer ve pilotun son hareket zamanını yeniler.
"""

import re
from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
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


def _fmt(value: float) -> str:
    return f"{value:g}".replace(".", ",")


def duration_days(timeline: str | None) -> int:
    """Brief'teki süre metninden ("3 ay", "6 hafta içinde") gün sayısı; anlaşılmazsa 90."""
    match = re.search(r"(\d+)\s*(gün|gun|hafta|ay)", (timeline or "").lower())
    if not match:
        return 90
    amount, unit = int(match.group(1)), match.group(2)
    return max(7, amount * {"gün": 1, "gun": 1, "hafta": 7, "ay": 30}[unit])


def metric_from_criteria(criteria: str | None) -> dict | None:
    """Başarı kriterinden ilk hedefi çıkarır: "%85 doğruluk" → hedef 85, birim %."""
    if not criteria or not criteria.strip():
        return None
    text = criteria.strip()
    direction = "azalis" if re.search(r"azal|düş|dus|indir|kısal|kisal", text.lower()) else "artis"
    number = re.search(r"%\s*(\d+(?:[.,]\d+)?)|(\d+(?:[.,]\d+)?)\s*%", text)
    target = float((number.group(1) or number.group(2)).replace(",", ".")) if number else None
    return {"name": text[:200], "unit": "%" if number else None, "target": target, "direction": direction}


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
    suggestion = metric_from_criteria(data.get("success_criteria"))
    if not has_metric and suggestion:
        session.add(PilotMetric(pilot_id=pilot.id, **suggestion))
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


def _progress(metric: PilotMetric, latest: float | None) -> tuple[float | None, bool | None]:
    if latest is None or metric.target is None:
        return None, None
    achieved = latest >= metric.target if metric.direction == "artis" else latest <= metric.target
    if metric.baseline is not None and metric.baseline != metric.target:
        share = (latest - metric.baseline) / (metric.target - metric.baseline)
    elif metric.direction == "artis" and metric.target:
        share = latest / metric.target
    else:
        return (1.0 if achieved else None), achieved
    return max(0.0, min(1.0, share)), achieved


def _metrics(session: Session, pilot: Pilot) -> list[api.MetricOut]:
    out = []
    for metric in session.scalars(select(PilotMetric).where(PilotMetric.pilot_id == pilot.id).order_by(PilotMetric.id)):
        rows = session.scalars(
            select(MetricMeasurement)
            .where(MetricMeasurement.metric_id == metric.id)
            .order_by(MetricMeasurement.measured_on, MetricMeasurement.id)
        ).all()
        latest = rows[-1].value if rows else None
        progress, achieved = _progress(metric, latest)
        out.append(
            api.MetricOut(
                id=metric.id,
                name=metric.name,
                unit=metric.unit,
                baseline=metric.baseline,
                target=metric.target,
                direction=metric.direction,
                latest=latest,
                progress=progress,
                achieved=achieved,
                measurements=[
                    api.MeasurementOut(id=r.id, value=r.value, measured_on=r.measured_on, note=r.note, author_role=r.author_role)
                    for r in rows
                ],
            )
        )
    return out


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


@router.post("/pilots/{pilot_id}/metrics", response_model=api.PilotDetailOut, summary="Ölçülebilir hedef ekle")
def add_metric(
    pilot_id: int,
    payload: api.MetricIn,
    session: Session = Depends(get_db),
    user: User = Depends(current_user),
    settings: Settings = Depends(get_settings),
):
    pilot = get_pilot(session, pilot_id, user)
    session.add(PilotMetric(pilot_id=pilot.id, **payload.model_dump()))
    target = f" (hedef {_fmt(payload.target)}{payload.unit or ''})" if payload.target is not None else ""
    log_event(session, pilot, f"Hedef eklendi: {_short(payload.name)}{target}", user)
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
    for field, value in payload.model_dump().items():
        setattr(metric, field, value)
    log_event(session, pilot, f"Hedef güncellendi: {_short(metric.name)}", user)
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
    session.delete(metric)
    session.commit()
    return pilot_detail(session, pilot, settings)


@router.post("/metrics/{metric_id}/measurements", response_model=api.PilotDetailOut, summary="Ölçüm ekle")
def add_measurement(
    metric_id: int,
    payload: api.MeasurementIn,
    session: Session = Depends(get_db),
    user: User = Depends(current_user),
    settings: Settings = Depends(get_settings),
):
    metric, pilot = _metric_pilot(session, metric_id, user)
    session.add(
        MetricMeasurement(
            metric_id=metric.id,
            value=payload.value,
            measured_on=payload.measured_on or _today(),
            note=(payload.note or "").strip() or None,
            author_role=ROLE_LABEL.get(user.role, "sistem"),
        )
    )
    log_event(session, pilot, f"Ölçüm: {_short(metric.name)} = {_fmt(payload.value)}{metric.unit or ''}", user)
    session.commit()
    return pilot_detail(session, pilot, settings)


@router.delete("/measurements/{measurement_id}", response_model=api.PilotDetailOut, summary="Ölçümü sil")
def delete_measurement(
    measurement_id: int,
    session: Session = Depends(get_db),
    user: User = Depends(current_user),
    settings: Settings = Depends(get_settings),
):
    row = session.get(MetricMeasurement, measurement_id)
    if row is None:
        raise HTTPException(404, "Ölçüm bulunamadı")
    metric, pilot = _metric_pilot(session, row.metric_id, user)
    session.delete(row)
    log_event(session, pilot, f"Ölçüm silindi: {_short(metric.name)} = {_fmt(row.value)}{metric.unit or ''}", user)
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
