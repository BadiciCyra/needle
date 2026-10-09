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
    note: str | None = Field(None, max_length=2000, description="Kabulde girişime giden tanıştırma notu")


class DecisionOut(BaseModel):
    match_id: int
    status: str
    introduction_id: int | None = None
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


IntroStatus = Literal["bekliyor", "kabul", "ret"]


class IntroBrief(BaseModel):
    """Tanıştırmada girişimle paylaşılan brief özeti."""

    title: str
    problem: str | None = None
    scope: str | None = None
    required_capabilities: list[str] = Field(default_factory=list)
    success_criteria: str | None = None
    timeline: str | None = None


class IntroEmail(BaseModel):
    """Tanıştırma e-postası taslağı (yalnızca firma ve yönetici görür)."""

    to: str | None
    subject: str
    body: str
    contact_source: str | None = Field(None, description="Alıcı adresinin bulunduğu sayfa")
    updated_at: datetime | None
    sent_at: datetime | None


class IntroEmailIn(BaseModel):
    to: str | None = Field(None, max_length=254)
    subject: str = Field(min_length=3, max_length=300)
    body: str = Field(min_length=10, max_length=10000)


class IntroEmailSentIn(BaseModel):
    sent: bool = True


class IntroductionOut(BaseModel):
    id: int
    status: IntroStatus
    brief_id: int
    brief: IntroBrief
    organization: str | None
    startup: StartupProfile
    startup_has_account: bool = Field(description="Girişimin doğrulanmış hesabı var mı (yoksa yönetici aracılık eder)")
    source: Literal["eslestirme", "cagri", "havuz"]
    firm_note: str | None
    startup_note: str | None
    responded_by: str | None
    created_at: datetime
    responded_at: datetime | None
    pilot_id: int | None = None
    email: IntroEmail | None = None


class DirectIntroIn(BaseModel):
    brief_id: int = Field(description="Tanışmanın konusu olan ihtiyaç")
    startup_id: str
    note: str | None = Field(None, max_length=2000, description="Girişime giden tanıştırma notu")


class IntroResponseIn(BaseModel):
    decision: Literal["kabul", "ret"]
    note: str | None = Field(None, max_length=2000)


class SavedMatchItem(MatchResultItem):
    match_id: int
    status: Literal["suggested", "accepted", "declined"]
    declined_reason: str | None = None
    introduction: IntroductionOut | None = None


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
    open_call_id: int | None = Field(None, description="Bu ihtiyaç için açılmış çağrı")


MilestoneOwner = Literal["kurum", "girisim", "ortak"]


class MilestoneIn(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    due_date: date | None = None
    owner: MilestoneOwner = "ortak"


class MilestoneEdit(BaseModel):
    title: str | None = Field(None, min_length=2, max_length=200)
    due_date: date | None = None
    owner: MilestoneOwner | None = None


class MilestoneOut(BaseModel):
    id: int
    title: str
    due_date: datetime | None
    completed_at: datetime | None
    owner: MilestoneOwner = "ortak"
    overdue: bool = False


PilotResult = Literal["evet", "kismen", "hayir"]
NextStep = Literal["satin_alma", "genisletme", "yeni_pilot", "bitir"]


class PilotUpdate(BaseModel):
    status: Literal["active", "paused", "done", "cancelled"] | None = None
    outcome: str | None = Field(None, description="Pilot sonucu (kapalı döngü için)")
    result: PilotResult | None = Field(None, description="İşe yaradı mı?")


class PilotPlanIn(BaseModel):
    goal: str | None = Field(None, max_length=2000)
    scope: str | None = Field(None, max_length=2000)
    start_date: date | None = None
    end_date: date | None = None
    firm_contact: str | None = Field(None, max_length=200)
    startup_contact: str | None = Field(None, max_length=200)


class MetricIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    unit: str | None = Field(None, max_length=30)
    baseline: float | None = None
    target: float | None = None
    direction: Literal["artis", "azalis"] = "artis"


class MeasurementIn(BaseModel):
    value: float
    measured_on: date | None = None
    note: str | None = Field(None, max_length=300)


class MeasurementOut(BaseModel):
    id: int
    value: float
    measured_on: date
    note: str | None
    author_role: str


class MetricOut(BaseModel):
    id: int
    name: str
    unit: str | None
    baseline: float | None
    target: float | None
    direction: Literal["artis", "azalis"]
    latest: float | None
    progress: float | None = Field(description="Hedefe ilerleme 0-1 (hesaplanabiliyorsa)")
    achieved: bool | None
    measurements: list[MeasurementOut]


class ActivityIn(BaseModel):
    body: str = Field(min_length=2, max_length=4000)


class ActivityOut(BaseModel):
    id: int
    kind: Literal["not", "olay"]
    author_role: str
    author_name: str | None
    body: str
    created_at: datetime


class PilotEvaluationIn(BaseModel):
    result: PilotResult
    next_step: NextStep
    startup_rating: int = Field(ge=1, le=5)
    comment: str | None = Field(None, max_length=4000)


class StartupFeedbackIn(BaseModel):
    feedback: str = Field(min_length=10, max_length=4000)
    collab_rating: int | None = Field(None, ge=1, le=5)


class PilotOut(BaseModel):
    id: int
    status: str
    match_id: int | None
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
    start_date: date | None = None
    end_date: date | None = None
    overdue_milestones: int = 0
    next_step: NextStep | None = None
    evaluated_at: datetime | None = None


class PilotDetailOut(PilotOut):
    goal: str | None
    scope: str | None
    firm_contact: str | None
    startup_contact: str | None
    startup_rating: int | None
    startup_feedback: str | None
    collab_rating: int | None
    startup_feedback_at: datetime | None
    metrics: list[MetricOut]
    activity: list[ActivityOut]


EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    email: str = Field(pattern=EMAIL_PATTERN, max_length=254)
    password: str = Field(min_length=10, max_length=200, description="En az 10 karakter")
    account_type: Literal["firma", "girisim"] = "firma"
    organization_name: str | None = Field(None, min_length=2, max_length=200, description="Firma hesabında zorunlu")
    kvkk_onay: bool = Field(description="Aydınlatma metninin okunduğunu onaylar")


class LoginIn(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=200)


class ResetRequestIn(BaseModel):
    email: str = Field(max_length=254)


class ResetConfirmIn(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    password: str = Field(min_length=10, max_length=200, description="En az 10 karakter")


class PasswordChangeIn(BaseModel):
    current_password: str = Field(max_length=200)
    new_password: str = Field(min_length=10, max_length=200, description="En az 10 karakter")


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
    description: str | None = Field(None, max_length=600, description="Firmanız ne iş yapıyor?")
    website: str | None = Field(None, max_length=300, pattern=r"^https?://")
    directory_visible: bool = Field(True, description="Kurumlar dizininde girişimlere görünsün mü")


class OrganizationOut(BaseModel):
    id: int
    name: str
    sector: str | None
    profile: dict
    onboarded: bool


class StartupAccountOut(BaseModel):
    id: str
    name: str
    status: Literal["aktif", "onay_bekliyor", "reddedildi"]
    verified: bool = Field(description="Hesap bu profilin sahibi olarak doğrulandı mı")


class MeOut(BaseModel):
    id: int
    name: str
    email: str
    role: Literal["firma", "yonetici", "girisim"]
    organization: OrganizationOut | None
    startup: StartupAccountOut | None = None


class ClaimIn(BaseModel):
    startup_id: str


class StartupProfileIn(BaseModel):
    """Girişimin kendi profili: yeni açarken ve düzenlerken."""

    name: str = Field(min_length=2, max_length=200)
    sector: str = Field(min_length=2, max_length=100)
    maturity: Maturity
    location: str = Field(min_length=2, max_length=100)
    website: str | None = Field(None, max_length=300, pattern=r"^https?://")
    description: str = Field(min_length=20, max_length=1500)
    capabilities: list[str] = Field(min_length=2, max_length=10, description="Kurumlara sunulan somut yetkinlikler")
    past_pilots: list[str] = Field(default_factory=list, max_length=10)


class ClaimOut(BaseModel):
    """Yöneticinin onay listesi: sahiplenme isteği ya da yeni profil."""

    user_id: int
    user_name: str
    email: str
    startup: StartupProfile
    startup_status: str
    kind: Literal["sahiplenme", "yeni_profil"]
    domain_match: bool
    created_at: datetime


class OpenCallIn(BaseModel):
    brief_id: int
    title: str = Field(min_length=5, max_length=200)
    summary: str = Field(min_length=20, max_length=3000, description="Girişimlerin göreceği metin")
    hide_organization: bool = False
    deadline: date | None = None


class OpenCallUpdate(BaseModel):
    status: Literal["acik", "kapali"]


class ApplicationIn(BaseModel):
    note: str = Field(min_length=20, max_length=3000, description="Bu problemi nasıl çözüyorsunuz?")


class ApplicationOut(BaseModel):
    id: int
    call_id: int
    startup: StartupProfile
    note: str
    status: Literal["yeni", "kabul", "ret"]
    decision_note: str | None
    created_at: datetime
    pilot_id: int | None = None


class ApplicationDecisionIn(BaseModel):
    decision: Literal["kabul", "ret"]
    note: str | None = Field(None, max_length=2000)


class OpenCallOut(BaseModel):
    id: int
    brief_id: int
    title: str
    summary: str
    organization: str | None = Field(description="Kurum adı gizlendiyse girişime None döner")
    sector: str | None
    required_capabilities: list[str]
    deadline: date | None
    status: Literal["acik", "kapali"]
    created_at: datetime
    hide_organization: bool
    application_count: int = 0
    my_application: ApplicationOut | None = Field(None, description="Girişim hesabı için kendi başvurusu")
    applications: list[ApplicationOut] = Field(default_factory=list, description="Firma ve yönetici için başvurular")


class DirectoryCall(BaseModel):
    id: int
    title: str
    deadline: date | None


class OrganizationCard(BaseModel):
    id: int
    name: str
    sector: str | None
    city: str | None
    employee_range: str | None
    description: str | None
    website: str | None
    open_calls: list[DirectoryCall] = Field(description="Kurum adını gizlemeyen açık çağrılar")
    joined_at: datetime | None


class RecommendedCall(BaseModel):
    id: int
    title: str
    organization: str | None
    deadline: date | None
    required_capabilities: list[str]
    score: float
    reason: str | None = Field(description="En yakın yetkinlik eşleşmesi")


class RecommendedOrganization(BaseModel):
    id: int
    name: str
    sector: str | None
    city: str | None
    open_calls: int
    score: float


class DemandSignal(BaseModel):
    capability: str
    organizations: int = Field(description="Bu yetkinliği arayan farklı kurum sayısı (en az 2)")
    variants: list[str]
    score: float


class StartupRecommendations(BaseModel):
    calls: list[RecommendedCall]
    organizations: list[RecommendedOrganization]
    signals: list[DemandSignal]


class RecommendedStartup(BaseModel):
    id: str
    name: str
    sector: str
    maturity: str
    location: str
    capabilities: list[str]
    score: float
    reason: str | None = Field(description="En yakın yetkinlik eşleşmesi")
    on_platform: bool = Field(description="Doğrulanmış girişim hesabı var; tanıştırmaya doğrudan cevap verebilir")
    applied: bool = Field(description="Kurumun açık çağrılarından birine başvurdu")


class OrganizationRecommendations(BaseModel):
    basis: list[str] = Field(description="Önerinin dayandığı aranan yetkinlikler")
    startups: list[RecommendedStartup]

