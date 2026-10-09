"""İkinci aşama sıralama: sorgu ile adayı birlikte okuyup yeniden puanlar.

- llm: adayları LLM puanlar ve en iyilerini "doğrudan çözüyor mu?" diye denetler (varsayılan)
- cross_encoder: yerel, açık kaynak, çok dilli mMARCO modeli
- none: sadece vektör / RRF sırası
"""

import math
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from typing import Protocol

from pydantic import BaseModel, Field

from app.config import Settings, get_settings
from app.llm.client import StructuredLLM
from app.schemas import Candidate


class Reranker(Protocol):
    name: str
    min_score: float
    relative_ratio: float

    def rerank(self, query: str, candidates: list[Candidate]) -> list[Candidate]:
        """rerank_score'u doldurur ve adayları azalan skora göre döndürür (0-1 arası)."""
        ...


class PassthroughReranker:
    name = "none"
    min_score = 0.0
    relative_ratio = 0.0

    def rerank(self, query: str, candidates: list[Candidate]) -> list[Candidate]:
        for candidate in candidates:
            candidate.rerank_score = candidate.vector_score
        return sorted(candidates, key=lambda c: c.rerank_score, reverse=True)


class CrossEncoderReranker:
    name = "cross_encoder"
    min_score = 0.003
    relative_ratio = 0.3

    def __init__(self, model_name: str):
        self.model_name = model_name
        self._model = None

    def _load(self):
        if self._model is None:
            from sentence_transformers import CrossEncoder

            self._model = CrossEncoder(self.model_name, max_length=512)
        return self._model

    def rerank(self, query: str, candidates: list[Candidate]) -> list[Candidate]:
        if not candidates:
            return []
        logits = self._load().predict([(query, c.startup.to_search_text()) for c in candidates])
        for candidate, logit in zip(candidates, logits):
            candidate.rerank_score = 1.0 / (1.0 + math.exp(-float(logit)))
        return sorted(candidates, key=lambda c: c.rerank_score, reverse=True)


class _LLMScore(BaseModel):
    startup_id: str
    score: int = Field(ge=0, le=10, description="0 = alakasız, 10 = ihtiyacı tam karşılıyor")


class _LLMScores(BaseModel):
    scores: list[_LLMScore]


class _Check(BaseModel):
    startup_id: str
    urun_ne_yapar: str = Field(description="Profile göre ürünün yaptığı iş, en fazla 12 kelime")
    ayni_nesne: bool = Field(description="Ürün, ihtiyacın nesnesiyle (aynı varlık / sistem / veri) mi çalışıyor?")
    ayni_is: bool = Field(description="Ürün, ihtiyaçta istenen işi (tespit, sınıflandırma, takip...) mi yapıyor?")
    uyarlama_gerekir: bool = Field(description="Kurumun kullanabilmesi için ürünün başka bir alana uyarlanması gerekir mi?")


class _Checks(BaseModel):
    ihtiyac_nesnesi: str = Field(description="İhtiyacın üzerinde çalıştığı varlık/sistem/veri, en fazla 8 kelime")
    istenen_is: str = Field(description="O nesne üzerinde yapılması istenen iş, en fazla 8 kelime")
    adaylar: list[_Check]


_SCORE_SYSTEM = (
    "Bir kurumun ihtiyacına en uygun girişimleri puanlıyorsun. Her girişime 0-10 arası puan ver. "
    "Sadece girişim profilinde yazan yetkinliklere dayan."
)

_CHECK_SYSTEM = """Bir kurumun ihtiyacı için öne çıkan girişimlerin bu problemi DOĞRUDAN çözüp çözmediğini denetliyorsun.
Önce ihtiyacın nesnesini ve istenen işi GENEL terimlerle yaz: kurumun kendi adlandırmasını değil, veri/varlık
türünü kullan (ör. "bayi şikayetleri" değil "müşteri şikayet metinleri"; "X belediyesinin boruları" değil
"su dağıtım şebekesi"). Sonra her girişim için yalnızca profilde yazanlara bakarak üç soruyu ayrı ayrı cevapla:
- ayni_nesne: ürün bu tür veri/varlıkla mı çalışıyor? Aynı teknoloji alanında olmak (IoT, görüntü işleme,
  kestirimci bakım, yapay zeka) yetmez; ör. fabrika makinesini izleyen sensör, şebeke borusunu izlemez → false.
- ayni_is: ürün istenen işin ÇEKİRDEĞİNİ yapıyor mu? İhtiyaç birkaç parçalıysa (ör. toplama + analiz + raporlama)
  ana parçayı yapması yeter. Benzer ama farklı iş (ör. müşteriye cevap veren sohbet botu ≠ şikayet sınıflandırma) → false.
- uyarlama_gerekir: ürünün başka bir alan veya nesne için yeniden geliştirilmesi gerekiyorsa true. Kurulum,
  entegrasyon, kurumun verisiyle eğitme veya ayar yapma uyarlama SAYILMAZ.
Emin değilsen ayni_nesne için false seç."""


def _is_direct(check: _Check) -> bool:
    return check.ayni_nesne and check.ayni_is and not check.uyarlama_gerekir


class LLMReranker:
    """İki aşama: (1) bütün adaylar 0-10 puanlanır, (2) en iyi `verify_top_n` aday "problemi doğrudan çözüyor mu?"
    diye ayrı bir çağrıda somut sorularla denetlenir; denetim `votes` kez paralel çalışır, çoğunluk oyu geçerlidir.

    Tek çağrıda 40 adaya tek bir evet/hayır sormak kararsızdı: aynı brief'te dört çalıştırmanın ikisi
    "uygun yok", ikisi 2-3 aday döndürüyordu (analiz/karar_kararliligi.py).
    """

    name = "llm"
    min_score = 0.5
    relative_ratio = 0.6

    def __init__(self, llm: StructuredLLM, verify_top_n: int = 8, votes: int = 3):
        self.llm = llm
        self.verify_top_n = verify_top_n
        self.votes = votes

    def rerank(self, query: str, candidates: list[Candidate]) -> list[Candidate]:
        if not candidates:
            return []
        self._score(query, candidates)
        ranked = sorted(candidates, key=lambda c: c.rerank_score, reverse=True)
        to_check = [c for c in ranked[: self.verify_top_n] if c.rerank_score >= self.min_score]
        checked = {c.startup.id for c in to_check}
        for candidate in ranked:
            candidate.direct_fit = False
            candidate.direct_fit_reason = None if candidate.startup.id in checked else "Denetlenmedi (puanı düşük)"
        if to_check:
            self._verify(query, to_check)
        return ranked

    def _score(self, query: str, candidates: list[Candidate]) -> None:
        listing = "\n\n".join(f"[{c.startup.id}]\n{c.startup.to_search_text()}" for c in candidates)
        result = self.llm.invoke(_LLMScores, system=_SCORE_SYSTEM, user=f"İhtiyaç:\n{query}\n\nGirişimler:\n{listing}")
        scores = {s.startup_id: s.score / 10 for s in result.scores}
        for candidate in candidates:
            candidate.rerank_score = scores.get(candidate.startup.id, 0.0)

    def _verify(self, query: str, candidates: list[Candidate]) -> None:
        listing = "\n\n".join(f"[{c.startup.id}]\n{c.startup.to_search_text()}" for c in candidates)
        user = f"İhtiyaç:\n{query}\n\nGirişimler:\n{listing}"
        with ThreadPoolExecutor(self.votes) as pool:
            rounds = list(pool.map(lambda _: self.llm.invoke(_Checks, system=_CHECK_SYSTEM, user=user), range(self.votes)))
        for candidate in candidates:
            checks = [c for r in rounds for c in r.adaylar if c.startup_id == candidate.startup.id]
            yes = [c for c in checks if _is_direct(c)]
            candidate.direct_fit = len(yes) * 2 > self.votes
            winner = (yes if candidate.direct_fit else [c for c in checks if not _is_direct(c)]) or checks
            if winner:
                candidate.direct_fit_reason = f"{winner[0].urun_ne_yapar} ({len(yes)}/{self.votes} oy evet)"


@lru_cache
def _cross_encoder(model_name: str) -> CrossEncoderReranker:
    return CrossEncoderReranker(model_name)


def get_reranker(settings: Settings | None = None, llm: StructuredLLM | None = None) -> Reranker:
    settings = settings or get_settings()
    if settings.rerank_backend == "cross_encoder":
        return _cross_encoder(settings.rerank_model)
    if settings.rerank_backend == "llm":
        if llm is None:
            from app.llm.client import get_structured_llm

            llm = get_structured_llm()
        return LLMReranker(llm, settings.rerank_verify_top_n, settings.rerank_verify_votes)
    return PassthroughReranker()
