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

    def rerank(self, query: str, candidates: list[Candidate]) -> list[Candidate]:
        """rerank_score'u doldurur ve adayları azalan skora göre döndürür (0-1 arası)."""
        ...


class PassthroughReranker:
    name = "none"

    def rerank(self, query: str, candidates: list[Candidate]) -> list[Candidate]:
        for candidate in candidates:
            candidate.rerank_score = candidate.vector_score
        return sorted(candidates, key=lambda c: c.rerank_score, reverse=True)


class CrossEncoderReranker:
    name = "cross_encoder"

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
    score: int = Field(ge=0, le=10, description="0 = alakasız, 10 = ihtiyacı tam karşılıyor")


class _LLMScores(BaseModel):
    scores: list[_LLMScore]


class LLMReranker:
    name = "llm"

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
                "Sadece girişim profilinde yazan yetkinliklere dayan."
            ),
            user=f"İhtiyaç:\n{query}\n\nGirişimler:\n{listing}",
        )
        scores = {s.startup_id: s.score / 10 for s in result.scores}
        for candidate in candidates:
            candidate.rerank_score = scores.get(candidate.startup.id, 0.0)
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
