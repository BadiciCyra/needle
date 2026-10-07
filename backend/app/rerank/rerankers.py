"""İkinci aşama sıralama: sorgu ile adayı birlikte okuyup yeniden puanlar.

- cross_encoder: yerel, açık kaynak, çok dilli mMARCO modeli (varsayılan)
- llm: adayları LLM puanlar (daha yavaş, daha pahalı)
- none: sadece vektör / RRF sırası
"""

import math
from functools import lru_cache
from typing import Protocol

from pydantic import BaseModel, Field

from app.config import Settings, get_settings
from app.llm.client import StructuredLLM
from app.schemas import Candidate


class Reranker(Protocol):
    name: str
    # Güven eşiği varsayılanları (match_graph.select_shortlist); her sıralayıcının skor ölçeğine göre
    min_score: float
    relative_ratio: float

    def rerank(self, query: str, candidates: list[Candidate]) -> list[Candidate]:
        """rerank_score'u doldurur ve adayları azalan skora göre döndürür (0-1 arası)."""
        ...


class PassthroughReranker:
    name = "none"
    min_score = 0.0  # kosinüs benzerliği mutlak alaka söylemez; kırpma yapılmaz
    relative_ratio = 0.0

    def rerank(self, query: str, candidates: list[Candidate]) -> list[Candidate]:
        for candidate in candidates:
            candidate.rerank_score = candidate.vector_score
        return sorted(candidates, key=lambda c: c.rerank_score, reverse=True)


class CrossEncoderReranker:
    name = "cross_encoder"
    min_score = 0.003  # analiz/esik_analizi.py: negatif ihtiyaçlarda birinci bile bunun altında kalıyor
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
            candidate.rerank_score = 1.0 / (1.0 + math.exp(-float(logit)))  # 0-1 aralığına sigmoid
        return sorted(candidates, key=lambda c: c.rerank_score, reverse=True)


class _LLMScore(BaseModel):
    startup_id: str
    # Gerekçe karardan önce: model önce ne yaptığını söyleyip sonra karar verince teğet adaylara daha az "evet" diyor
    gerekce: str = Field(description="En fazla 15 kelime: girişimin ürünü bu problemde tam olarak ne yapar?")
    dogrudan_cozer: bool = Field(description="Ürünü, ihtiyaçtaki problemi bugün olduğu haliyle doğrudan çözüyor mu?")
    score: int = Field(ge=0, le=10, description="0 = alakasız, 10 = ihtiyacı tam karşılıyor")


class _LLMScores(BaseModel):
    scores: list[_LLMScore]


class LLMReranker:
    name = "llm"
    # 0-10 puanın onda biri: birinci 4/10 veya altındaysa "güçlü eşleşme yok"; birincinin %60'ının
    # altındakiler kırpılır (ör. 9/10 birinciyken 5/10 ve altı listeye girmez)
    min_score = 0.5
    relative_ratio = 0.6

    def __init__(self, llm: StructuredLLM):
        self.llm = llm

    def rerank(self, query: str, candidates: list[Candidate]) -> list[Candidate]:
        if not candidates:
            return []
        listing = "\n\n".join(f"[{c.startup.id}]\n{c.startup.to_search_text()}" for c in candidates)
        result = self.llm.invoke(
            _LLMScores,
            system=(
                "Bir kurumun ihtiyacına en uygun girişimleri puanlıyorsun. Her girişime 0-10 arası puan ver. "
                "Sadece girişim profilinde yazan yetkinliklere dayan.\n"
                "dogrudan_cozer: girişimin profilde yazan ürünü, ihtiyaçtaki problemin nesnesiyle/süreciyle/verisiyle "
                "çalışıyor ve kurum onu bu iş için yeni bir ürün geliştirmeden kullanabiliyorsa true. Yalnızca aynı "
                "teknoloji alanında olmak (ör. ikisi de IoT, görüntü işleme, kestirimci bakım veya veri analitiği) "
                "veya 'uyarlanabilir' olmak yetmez; o durumda false. Emin değilsen false."
            ),
            user=f"İhtiyaç:\n{query}\n\nGirişimler:\n{listing}",
        )
        by_id = {s.startup_id: s for s in result.scores}
        for candidate in candidates:
            s = by_id.get(candidate.startup.id)
            candidate.rerank_score = s.score / 10 if s else 0.0
            candidate.direct_fit = s.dogrudan_cozer if s else False
            candidate.direct_fit_reason = s.gerekce if s else None
        return sorted(candidates, key=lambda c: c.rerank_score, reverse=True)


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
        return LLMReranker(llm)
    return PassthroughReranker()
