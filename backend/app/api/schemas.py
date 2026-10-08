"""API istek / cevap şemaları."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas import Brief, FollowUpQuestion, Maturity, MatchResult, MatchResultItem, StartupProfile, TraceStep


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
    no_match: bool = False
    retrieval_trace: list[str]
    trace_steps: list[TraceStep] = Field(default_factory=list, description="Eski kayıtlarda boş (iz düz metindi)")


class MilestoneIn(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    due_date: date | None = None


class MilestoneOut(BaseModel):
    id: int
    title: str
    due_date: datetime | None
    completed_at: datetime | None


PilotResult = Literal["evet", "kismen", "hayir"]


class PilotUpdate(BaseModel):
    status: Literal["active", "paused", "done", "cancelled"] | None = None
    outcome: str | None = Field(None, description="Pilot sonucu (kapalı döngü için)")
    result: PilotResult | None = Field(None, description="İşe yaradı mı?")


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
    result: PilotResult | None
    milestones: list[MilestoneOut]
    organization: str | None = None


# --------------------------------------------------------------------------- #
# Hesaplar ve firma profili
# --------------------------------------------------------------------------- #

EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    email: str = Field(pattern=EMAIL_PATTERN, max_length=254)
    password: str = Field(min_length=10, max_length=200, description="En az 10 karakter")
    organization_name: str = Field(min_length=2, max_length=200)
    kvkk_onay: bool = Field(description="Aydınlatma metninin okunduğunu onaylar")


class LoginIn(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=200)


class OrgProfile(BaseModel):
    """Firma hesabının ilk girişte doldurduğu profil. Brief'in boş alanlarını doldurmak için kullanılır."""

    sector: str = Field(min_length=2, max_length=100)
    city: str = Field(min_length=2, max_length=100)
    employee_range: Literal["1-49", "50-249", "250-999", "1000+"]
    systems: list[str] = Field(default_factory=list, max_length=12, description="Kullanılan sistemler (ERP, CRM…)")
    preferred_maturity: Maturity | None = Field(None, description="Çalışmak istenen en düşük girişim olgunluğu")
    startup_location: Literal["ayni_sehir", "fark_etmez"] = "fark_etmez"
    budget_range: str | None = Field(None, max_length=100)
    pilot_duration: str | None = Field(None, max_length=100)
    data_constraints: list[str] = Field(default_factory=list, max_length=8)


class OrganizationOut(BaseModel):
    id: int
    name: str
    sector: str | None
    profile: dict
    onboarded: bool


class MeOut(BaseModel):
    id: int
    name: str
    email: str
    role: Literal["firma", "yonetici"]
    organization: OrganizationOut | None
