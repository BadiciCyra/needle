"""API istek / cevap şemaları."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas import Brief, FollowUpQuestion, MatchResult, MatchResultItem, StartupProfile


class OrganizationIn(BaseModel):
    name: str
    sector: str | None = None
    author_unit: str | None = Field(None, description="İhtiyacı yazan birim")
    owner_unit: str | None = Field(None, description="İhtiyacı yaşayan birim")


class NeedIn(BaseModel):
    raw_text: str = Field(min_length=10, description="Kurumun serbest yazdığı ihtiyaç metni")
    organization: OrganizationIn | None = None


class AnswersIn(BaseModel):
    answers: dict[str, str] = Field(description="Alan adı → cevap (takip sorularındaki field değerleri)")


class BriefOut(BaseModel):
    brief_id: int
    need_id: int
    status: Literal["needs_input", "final"]
    brief: Brief
    questions: list[FollowUpQuestion]


class MatchOut(MatchResult):
    run_id: int
    match_ids: dict[str, int] = Field(description="startup_id → match_id (karar vermek için)")


class DecisionIn(BaseModel):
    decision: Literal["accept", "decline"]
    reason: str | None = Field(None, description="Ret sebebi (negatif eşleşme kaydı için)")


class DecisionOut(BaseModel):
    match_id: int
    status: str
    pilot_id: int | None = None


class NeedSummary(BaseModel):
    brief_id: int
    need_id: int
    title: str
    status: Literal["needs_input", "final"]
    raw_text: str
    organization: str | None = None
    created_at: datetime
    shortlist_count: int = Field(0, description="Son eşleştirme turundaki kısa liste boyu")
    accepted_count: int = 0


class SavedMatchItem(MatchResultItem):
    match_id: int
    status: Literal["suggested", "accepted", "declined"]
    declined_reason: str | None = None


class SavedMatchOut(BaseModel):
    """Son eşleştirme turu, LLM'i yeniden çağırmadan veritabanından."""

    brief_id: int
    run_id: int
    created_at: datetime
    shortlist: list[SavedMatchItem]
    rejected: list[SavedMatchItem]
    retrieval_trace: list[str]


class MilestoneIn(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    due_date: date | None = None


class MilestoneOut(BaseModel):
    id: int
    title: str
    due_date: datetime | None
    completed_at: datetime | None


class PilotUpdate(BaseModel):
    status: Literal["active", "paused", "done", "cancelled"] | None = None
    outcome: str | None = Field(None, description="Pilot sonucu (kapalı döngü için)")
    outcome_score: float | None = Field(None, ge=0, le=10)


class PilotOut(BaseModel):
    id: int
    status: str
    match_id: int
    brief_id: int
    brief_title: str
    startup: StartupProfile
    started_at: datetime
    last_activity_at: datetime
    days_inactive: int
    stale: bool = Field(description="Aktif ve pilot_stale_days gündür hareketsiz")
    outcome: str | None
    outcome_score: float | None
    milestones: list[MilestoneOut]
