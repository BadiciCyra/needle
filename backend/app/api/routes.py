"""Needle API uç noktaları."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api import schemas as api
from app.api.collab_routes import call_id_for_brief, intro_email_draft, intro_out, verified_owner
from app.api.deps import embedder_dep, llm_dep, reranker_dep, retriever_dep
from app.auth import current_user, ensure_visible, org_scope
from app.config import Settings, get_settings
from app.db.models import (
    BriefRecord,
    Introduction,
    Match,
    MatchRun,
    Need,
    Organization,
    Startup,
    User,
)
from app.db.session import get_db
from app.embeddings import Embedder
from app.graphs.brief_graph import build_brief_graph, profile_defaults
from app.graphs.match_graph import build_match_graph
from app.llm.client import StructuredLLM
from app.rerank.rerankers import Reranker
from app.retrieval.base import Retriever
from app.retrieval.pgvector import to_profile
from app.schemas import Brief, FollowUpQuestion, StartupProfile, TraceStep

router = APIRouter()


def _brief_out(record: BriefRecord) -> api.BriefOut:
    return api.BriefOut(
        brief_id=record.id,
        need_id=record.need_id,
        status=record.status,
        brief=Brief.model_validate(record.data),
        questions=[FollowUpQuestion.model_validate(q) for q in record.followup_questions]
        if record.status == "needs_input"
        else [],
    )


def _apply_brief_state(record: BriefRecord, state: dict, embedder: Embedder) -> None:
    record.data = state["brief"]
    record.status = state["status"]
    if state["status"] == "needs_input":
        record.followup_questions = state["questions"]
    if state["status"] == "final":
        record.embedding = embedder.embed_query(Brief.model_validate(state["brief"]).to_search_text())


def _get_brief(session: Session, brief_id: int, user: User) -> BriefRecord:
    """Brief'i getirir; firma kullanıcısı yalnızca kendi kurumunun brief'ine erişebilir."""
    record = session.get(BriefRecord, brief_id)
    if record is None:
        raise HTTPException(404, "Brief bulunamadı")
    ensure_visible(user, record.need.organization_id)
    return record


def _defaults_for(session: Session, organization_id: int | None) -> dict:
    organization = session.get(Organization, organization_id) if organization_id else None
    return profile_defaults(organization.profile if organization else None)


@router.post("/needs", response_model=api.BriefOut, summary="İhtiyaç metninden brief üret")
def create_need(
    payload: api.NeedIn,
    session: Session = Depends(get_db),
    user: User = Depends(current_user),
    llm: StructuredLLM = Depends(llm_dep),
    embedder: Embedder = Depends(embedder_dep),
    settings: Settings = Depends(get_settings),
):
    if user.role == "firma":
        organization_id = user.organization_id
    elif payload.organization:
        organization = Organization(**payload.organization.model_dump())
        session.add(organization)
        session.flush()
        organization_id = organization.id
    else:
        organization_id = None

    need = Need(raw_text=payload.raw_text, organization_id=organization_id)
    session.add(need)
    session.flush()

    state = build_brief_graph(llm, settings).invoke(
        {"raw_text": payload.raw_text, "defaults": _defaults_for(session, organization_id)}
    )
    record = BriefRecord(need_id=need.id, data={}, followup_questions=[], answers={})
    _apply_brief_state(record, state, embedder)
    session.add(record)
    session.commit()
    return _brief_out(record)


@router.post("/briefs/{brief_id}/answers", response_model=api.BriefOut, summary="Takip sorularını cevapla")
def answer_followups(
    brief_id: int,
    payload: api.AnswersIn,
    session: Session = Depends(get_db),
    user: User = Depends(current_user),
    llm: StructuredLLM = Depends(llm_dep),
    embedder: Embedder = Depends(embedder_dep),
    settings: Settings = Depends(get_settings),
):
    record = _get_brief(session, brief_id, user)
    if record.status != "needs_input":
        raise HTTPException(409, "Bu brief takip sorusu beklemiyor")

    state = build_brief_graph(llm, settings).invoke(
        {
            "raw_text": record.need.raw_text,
            "answers": payload.answers,
            "asked_questions": record.followup_questions,
            "followup_rounds": 1,
            "defaults": _defaults_for(session, record.need.organization_id),
        }
    )
    record.answers = payload.answers
    _apply_brief_state(record, state, embedder)
    session.commit()
    return _brief_out(record)


@router.get("/briefs/{brief_id}", response_model=api.BriefOut, summary="Brief'in son hali")
def get_brief(brief_id: int, session: Session = Depends(get_db), user: User = Depends(current_user)):
    return _brief_out(_get_brief(session, brief_id, user))


def _latest_run(session: Session, brief_id: int) -> MatchRun | None:
    return session.scalars(
        select(MatchRun).where(MatchRun.brief_id == brief_id).order_by(MatchRun.id.desc()).limit(1)
    ).first()


@router.get("/needs", response_model=list[api.NeedSummary], summary="İhtiyaçlar (en yeni önce)")
def list_needs(session: Session = Depends(get_db), user: User = Depends(current_user)):
    query = (
        select(BriefRecord, Need, Organization.name)
        .join(Need, BriefRecord.need_id == Need.id)
        .outerjoin(Organization, Need.organization_id == Organization.id)
        .order_by(BriefRecord.id.desc())
    )
    scope = org_scope(user)
    if scope is not None:
        query = query.where(Need.organization_id == scope)
    rows = session.execute(query).all()
    out = []
    for record, need, organization in rows:
        run = _latest_run(session, record.id)
        counts = dict(
            session.execute(
                select(Match.status, func.count()).where(Match.run_id == run.id, Match.kind == "shortlist").group_by(Match.status)
            ).all()
        ) if run else {}
        out.append(
            api.NeedSummary(
                brief_id=record.id,
                need_id=need.id,
                title=(record.data or {}).get("title") or need.raw_text[:60],
                status=record.status,
                raw_text=need.raw_text,
                organization=organization,
                created_at=need.created_at,
                shortlist_count=sum(counts.values()),
                accepted_count=counts.get("accepted", 0),
            )
        )
    return out


@router.get("/briefs/{brief_id}/match", response_model=api.SavedMatchOut, summary="Son eşleştirme sonucu")
def get_latest_match(brief_id: int, session: Session = Depends(get_db), user: User = Depends(current_user)):
    _get_brief(session, brief_id, user)
    run = _latest_run(session, brief_id)
    if run is None:
        raise HTTPException(404, "Bu brief için henüz eşleştirme yapılmadı")
    rows = session.execute(
        select(Match, Startup).join(Startup, Match.startup_id == Startup.id).where(Match.run_id == run.id).order_by(Match.rank)
    ).all()
    items: dict[str, list[api.SavedMatchItem]] = {"shortlist": [], "rejected": []}
    intros = {
        i.match_id: i
        for i in session.scalars(
            select(Introduction).where(Introduction.match_id.in_([m.id for m, _ in rows]))
        ).all()
    }
    for match, startup in rows:
        intro = intros.get(match.id)
        items[match.kind].append(
            api.SavedMatchItem(
                match_id=match.id,
                status=match.status,
                rank=match.rank,
                startup=to_profile(startup),
                score=match.score,
                vector_score=match.vector_score,
                rationale=match.rationale,
                rejection=match.rejection if match.rejection and "near_miss_reason" in match.rejection else None,
                declined_reason=(match.rejection or {}).get("declined_reason"),
                introduction=intro_out(session, intro, user) if intro else None,
            )
        )
    return api.SavedMatchOut(
        brief_id=brief_id,
        run_id=run.id,
        created_at=run.created_at,
        no_match=not items["shortlist"],
        retrieval_trace=[s["message"] if isinstance(s, dict) else s for s in run.trace],
        trace_steps=[TraceStep.model_validate(s) for s in run.trace if isinstance(s, dict)],
        open_call_id=call_id_for_brief(session, brief_id),
        **items,
    )


@router.post("/briefs/{brief_id}/match", response_model=api.MatchOut, summary="Gerekçeli eşleştirme")
def match_brief(
    brief_id: int,
    session: Session = Depends(get_db),
    user: User = Depends(current_user),
    retriever: Retriever = Depends(retriever_dep),
    embedder: Embedder = Depends(embedder_dep),
    reranker: Reranker = Depends(reranker_dep),
    llm: StructuredLLM = Depends(llm_dep),
    settings: Settings = Depends(get_settings),
):
    record = _get_brief(session, brief_id, user)
    if record.status != "final":
        raise HTTPException(409, "Önce takip sorularını cevaplayın; brief henüz tamamlanmadı")

    graph = build_match_graph(retriever, embedder, reranker, llm, settings)
    result = graph.invoke({"brief": record.data})["result"]

    run = MatchRun(brief_id=brief_id, trace=[step.model_dump(exclude_none=True) for step in result.trace_steps])
    session.add(run)
    session.flush()

    match_ids: dict[str, int] = {}
    for kind, items in (("shortlist", result.shortlist), ("rejected", result.rejected)):
        for item in items:
            match = Match(
                run_id=run.id,
                brief_id=brief_id,
                startup_id=item.startup.id,
                kind=kind,
                rank=item.rank,
                score=item.score,
                vector_score=item.vector_score,
                rerank_score=item.rerank_score,
                rationale=item.rationale.model_dump() if item.rationale else None,
                rejection=item.rejection.model_dump() if item.rejection else None,
            )
            session.add(match)
            session.flush()
            match_ids[item.startup.id] = match.id
    session.commit()

    return api.MatchOut(**{**result.model_dump(), "brief_id": brief_id}, run_id=run.id, match_ids=match_ids)


@router.post("/matches/{match_id}/decision", response_model=api.DecisionOut, summary="Eşleşmeyi kabul et / reddet")
def decide_match(
    match_id: int,
    payload: api.DecisionIn,
    session: Session = Depends(get_db),
    user: User = Depends(current_user),
    settings: Settings = Depends(get_settings),
):
    match = session.get(Match, match_id)
    if match is None:
        raise HTTPException(404, "Eşleşme bulunamadı")
    _get_brief(session, match.brief_id, user)
    if match.status != "suggested":
        raise HTTPException(409, f"Bu eşleşme için zaten karar verilmiş: {match.status}")

    match.decided_at = datetime.now(timezone.utc)
    introduction_id = None
    if payload.decision == "accept":
        match.status = "accepted"
        intro = Introduction(
            brief_id=match.brief_id, startup_id=match.startup_id, match_id=match.id, firm_note=payload.note
        )
        session.add(intro)
        session.flush()
        if verified_owner(session, match.startup_id) is None:
            intro_email_draft(session, intro, user, settings)
        introduction_id = intro.id
    else:
        match.status = "declined"
        if payload.reason:
            match.rejection = {
                **(match.rejection or {}),
                "startup_id": match.startup_id,
                "declined_reason": payload.reason,
            }
    session.commit()
    return api.DecisionOut(match_id=match.id, status=match.status, introduction_id=introduction_id)


@router.post("/introductions", response_model=api.IntroductionOut, summary="Havuzdan doğrudan tanışma iste")
def create_direct_introduction(
    payload: api.DirectIntroIn,
    session: Session = Depends(get_db),
    user: User = Depends(current_user),
    settings: Settings = Depends(get_settings),
):
    """Firma, eşleştirmenin önermediği bir girişimle de kendi ihtiyacı için tanışma isteyebilir.

    Aynı ihtiyaç ve girişim için bekleyen ya da kabul edilmiş bir tanışma varsa yenisi açılmaz. Girişim bu
    ihtiyacın kısa listesinde öneri olarak duruyorsa öneri kabul edilmiş sayılır ve tanışmaya bağlanır.
    """
    org_scope(user)
    record = _get_brief(session, payload.brief_id, user)
    startup = session.get(Startup, payload.startup_id)
    if startup is None or startup.status != "aktif":
        raise HTTPException(404, "Girişim bulunamadı")
    existing = session.scalar(
        select(Introduction).where(
            Introduction.brief_id == record.id,
            Introduction.startup_id == startup.id,
            Introduction.status.in_(["bekliyor", "kabul"]),
        )
    )
    if existing is not None:
        raise HTTPException(409, "Bu ihtiyaç için bu girişimle zaten bir tanışma var")

    match = session.scalar(
        select(Match).where(Match.brief_id == record.id, Match.startup_id == startup.id, Match.status == "suggested")
    )
    if match is not None:
        match.status = "accepted"
        match.decided_at = datetime.now(timezone.utc)
    intro = Introduction(
        brief_id=record.id, startup_id=startup.id, match_id=match.id if match else None, firm_note=payload.note
    )
    session.add(intro)
    session.flush()
    if verified_owner(session, startup.id) is None:
        intro_email_draft(session, intro, user, settings)
    session.commit()
    return intro_out(session, intro, user)


@router.get("/startups", response_model=list[StartupProfile], summary="Girişim havuzu")
def list_startups(session: Session = Depends(get_db), _: User = Depends(current_user)):
    rows = session.scalars(select(Startup).where(Startup.status == "aktif").order_by(Startup.id)).all()
    return [to_profile(row) for row in rows]
