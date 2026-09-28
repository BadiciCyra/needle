"""Needle API uç noktaları."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api import schemas as api
from app.api.deps import embedder_dep, llm_dep, reranker_dep, retriever_dep
from app.config import Settings, get_settings
from app.db.models import BriefRecord, Match, MatchRun, Need, Organization, Pilot, Startup
from app.db.session import get_db
from app.embeddings import Embedder
from app.graphs.brief_graph import build_brief_graph
from app.graphs.match_graph import build_match_graph
from app.llm.client import StructuredLLM
from app.rerank.rerankers import Reranker
from app.retrieval.base import Retriever
from app.retrieval.pgvector import to_profile
from app.schemas import Brief, FollowUpQuestion, StartupProfile

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


def _get_brief(session: Session, brief_id: int) -> BriefRecord:
    record = session.get(BriefRecord, brief_id)
    if record is None:
        raise HTTPException(404, "Brief bulunamadı")
    return record


@router.post("/needs", response_model=api.BriefOut, summary="İhtiyaç metninden brief üret")
def create_need(
    payload: api.NeedIn,
    session: Session = Depends(get_db),
    llm: StructuredLLM = Depends(llm_dep),
    embedder: Embedder = Depends(embedder_dep),
    settings: Settings = Depends(get_settings),
):
    organization_id = None
    if payload.organization:
        organization = Organization(**payload.organization.model_dump())
        session.add(organization)
        session.flush()
        organization_id = organization.id

    need = Need(raw_text=payload.raw_text, organization_id=organization_id)
    session.add(need)
    session.flush()

    state = build_brief_graph(llm, settings).invoke({"raw_text": payload.raw_text})
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
    llm: StructuredLLM = Depends(llm_dep),
    embedder: Embedder = Depends(embedder_dep),
    settings: Settings = Depends(get_settings),
):
    record = _get_brief(session, brief_id)
    if record.status != "needs_input":
        raise HTTPException(409, "Bu brief takip sorusu beklemiyor")

    state = build_brief_graph(llm, settings).invoke(
        {
            "raw_text": record.need.raw_text,
            "answers": payload.answers,
            "asked_questions": record.followup_questions,
            "followup_rounds": 1,
        }
    )
    record.answers = payload.answers
    _apply_brief_state(record, state, embedder)
    session.commit()
    return _brief_out(record)


@router.get("/briefs/{brief_id}", response_model=api.BriefOut, summary="Brief'in son hali")
def get_brief(brief_id: int, session: Session = Depends(get_db)):
    return _brief_out(_get_brief(session, brief_id))


@router.post("/briefs/{brief_id}/match", response_model=api.MatchOut, summary="Gerekçeli eşleştirme")
def match_brief(
    brief_id: int,
    session: Session = Depends(get_db),
    retriever: Retriever = Depends(retriever_dep),
    embedder: Embedder = Depends(embedder_dep),
    reranker: Reranker = Depends(reranker_dep),
    llm: StructuredLLM = Depends(llm_dep),
    settings: Settings = Depends(get_settings),
):
    record = _get_brief(session, brief_id)
    if record.status != "final":
        raise HTTPException(409, "Önce takip sorularını cevaplayın; brief henüz tamamlanmadı")

    graph = build_match_graph(retriever, embedder, reranker, llm, settings)
    result = graph.invoke({"brief": record.data})["result"]

    run = MatchRun(brief_id=brief_id, trace=result.retrieval_trace)
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
                rerank_score=item.score,
                rationale=item.rationale.model_dump() if item.rationale else None,
                rejection=item.rejection.model_dump() if item.rejection else None,
            )
            session.add(match)
            session.flush()
            match_ids[item.startup.id] = match.id
    session.commit()

    return api.MatchOut(**{**result.model_dump(), "brief_id": brief_id}, run_id=run.id, match_ids=match_ids)


@router.post("/matches/{match_id}/decision", response_model=api.DecisionOut, summary="Eşleşmeyi kabul et / reddet")
def decide_match(match_id: int, payload: api.DecisionIn, session: Session = Depends(get_db)):
    match = session.get(Match, match_id)
    if match is None:
        raise HTTPException(404, "Eşleşme bulunamadı")
    if match.status != "suggested":
        raise HTTPException(409, f"Bu eşleşme için zaten karar verilmiş: {match.status}")

    match.decided_at = datetime.now(timezone.utc)
    pilot_id = None
    if payload.decision == "accept":
        match.status = "accepted"
        pilot = Pilot(match_id=match.id)  # kabul edilen eşleşme için pilot kartı otomatik açılır
        session.add(pilot)
        session.flush()
        pilot_id = pilot.id
    else:
        match.status = "declined"
        if payload.reason:
            match.rejection = {
                **(match.rejection or {}),
                "startup_id": match.startup_id,
                "declined_reason": payload.reason,
            }
    session.commit()
    return api.DecisionOut(match_id=match.id, status=match.status, pilot_id=pilot_id)


@router.get("/startups", response_model=list[StartupProfile], summary="Girişim havuzu")
def list_startups(session: Session = Depends(get_db)):
    rows = session.scalars(select(Startup).order_by(Startup.id)).all()
    return [to_profile(row) for row in rows]
