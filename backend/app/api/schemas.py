"""API istek / cevap şemaları."""

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas import Brief, FollowUpQuestion, MatchResult


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
