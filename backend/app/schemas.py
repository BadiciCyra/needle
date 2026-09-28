"""Needle'ın ortak veri şemaları.

LLM çıktıları da bu şemalarla doğrulanır: şemaya uymayan cevap reddedilip yeniden istenir.
"""

from enum import Enum

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------- #
# Ortak sözlükler
# --------------------------------------------------------------------------- #

class Maturity(str, Enum):
    """Girişimin olgunluk seviyesi."""

    idea = "fikir"
    prototype = "prototip"
    mvp = "mvp"
    early_revenue = "ilk_gelir"
    growth = "buyume"


# Brief'te dolu olması gereken alanlar. Eksikse takip sorusu sorulur.
REQUIRED_BRIEF_FIELDS = ("problem", "scope", "required_capabilities", "success_criteria", "timeline")


# --------------------------------------------------------------------------- #
# Brief (Adım 1)
# --------------------------------------------------------------------------- #

class Brief(BaseModel):
    """Kurumun serbest metninden çıkarılan yapılandırılmış ihtiyaç."""

    title: str = Field(description="İhtiyacın kısa başlığı, en fazla 10 kelime")
    problem: str | None = Field(None, description="Çözülmesi gereken asıl problem")
    scope: str | None = Field(None, description="Kapsam: hangi birim, hangi veri, hangi sistem, ne kadar hacim")
    required_capabilities: list[str] = Field(
        default_factory=list,
        description="Girişimde aranan yetkinlikler, her biri kısa bir ifade (ör. 'Türkçe metin sınıflandırma')",
    )
    sector: str | None = Field(None, description="Kurumun sektörü (ör. perakende, enerji, sağlık)")
    success_criteria: str | None = Field(None, description="Pilotun başarılı sayılması için ölçülebilir kriter")
    timeline: str | None = Field(None, description="Beklenen süre (ör. '3 aylık pilot')")
    budget: str | None = Field(None, description="Bütçe bilgisi, metinde varsa")
    location_preference: str | None = Field(None, description="Girişim için lokasyon tercihi, varsa")
    min_maturity: Maturity | None = Field(None, description="Girişimde beklenen en düşük olgunluk, varsa")
    missing_fields: list[str] = Field(
        default_factory=list,
        description="Metinden çıkarılamayan zorunlu alanların adları",
    )

    def computed_missing_fields(self) -> list[str]:
        """Zorunlu alanlardan boş kalanları hesaplar (LLM'in beyanına güvenmeden)."""
        missing = []
        for name in REQUIRED_BRIEF_FIELDS:
            value = getattr(self, name)
            if value is None or value == "" or value == []:
                missing.append(name)
        return missing

    def to_search_text(self) -> str:
        """Embedding için tek bir metne çevirir."""
        parts = [self.title, self.problem or "", self.scope or "", " ; ".join(self.required_capabilities)]
        if self.sector:
            parts.append(f"Sektör: {self.sector}")
        return "\n".join(p for p in parts if p)


class FollowUpQuestion(BaseModel):
    field: str = Field(description="Sorunun doldurmaya çalıştığı brief alanı")
    question: str = Field(description="Kuruma sorulacak kısa, net soru")


class FollowUpQuestions(BaseModel):
    questions: list[FollowUpQuestion]


# --------------------------------------------------------------------------- #
# Girişim profili
# --------------------------------------------------------------------------- #

class StartupProfile(BaseModel):
    id: str
    name: str
    sector: str
    maturity: Maturity
    location: str
    capabilities: list[str]
    description: str
    past_pilots: list[str] = Field(default_factory=list)

    def to_search_text(self) -> str:
        return "\n".join(
            [
                self.name,
                self.description,
                "Yetkinlikler: " + " ; ".join(self.capabilities),
                f"Sektör: {self.sector}",
            ]
        )


# --------------------------------------------------------------------------- #
# Eşleştirme (Adım 2)
# --------------------------------------------------------------------------- #

class Candidate(BaseModel):
    """Retrieval'dan dönen aday; skorlar aşama aşama doldurulur."""

    startup: StartupProfile
    vector_score: float = 0.0
    rerank_score: float | None = None
    filter_notes: list[str] = Field(default_factory=list, description="Hangi filtreye takıldı / hangisi gevşetildi")


class EvidenceLink(BaseModel):
    """Gerekçe izi: brief'teki bir ifade ↔ girişimin bir yetkinliği."""

    brief_phrase: str = Field(description="Brief'ten birebir alınmış kısa ifade")
    startup_capability: str = Field(description="Girişim profilinden birebir alınmış yetkinlik")
    explanation: str = Field(description="Neden örtüştüğü, tek cümle")


class MatchRationale(BaseModel):
    startup_id: str
    fit_summary: str = Field(description="Neden uygun, en fazla 2 cümle")
    evidence: list[EvidenceLink] = Field(description="1-3 gerekçe izi")


class RejectionRationale(BaseModel):
    """Negatif eşleşme: yakındı ama olmadı, çünkü X."""

    startup_id: str
    near_miss_reason: str = Field(description="'Yakındı ama ... çünkü ...' formatında tek cümle")
    missing_capability: str | None = Field(None, description="Eksik kalan yetkinlik, varsa")


class RationaleBatch(BaseModel):
    matches: list[MatchRationale]
    rejections: list[RejectionRationale]


class MatchResultItem(BaseModel):
    rank: int
    startup: StartupProfile
    score: float
    vector_score: float = 0.0
    rationale: MatchRationale | None = None
    rejection: RejectionRationale | None = None
    filter_notes: list[str] = Field(default_factory=list, description="Kurumun tercihi dışında kalan noktalar")


class MatchResult(BaseModel):
    brief_id: int | None = None
    shortlist: list[MatchResultItem]
    rejected: list[MatchResultItem]
    retrieval_trace: list[str] = Field(
        default_factory=list, description="Dinamik RAG'in hangi turda ne yaptığının kaydı (şeffaflık için)"
    )
