"""Retrieval arayüzü. Her arka uç (pgvector, bellek içi, ileride anahtar kelime / web) bunu uygular."""

from dataclasses import dataclass, field
from typing import Protocol

from app.schemas import Candidate, Maturity

MATURITY_ORDER: list[Maturity] = [
    Maturity.idea,
    Maturity.prototype,
    Maturity.mvp,
    Maturity.early_revenue,
    Maturity.growth,
]


def maturities_at_least(minimum: Maturity | None) -> list[str] | None:
    if minimum is None:
        return None
    return [m.value for m in MATURITY_ORDER[MATURITY_ORDER.index(minimum) :]]


@dataclass(frozen=True)
class SearchFilters:
    location: str | None = None
    min_maturity: Maturity | None = None
    exclude_ids: frozenset[str] = frozenset()

    def describe(self) -> str:
        parts = []
        if self.location:
            parts.append(f"lokasyon={self.location}")
        if self.min_maturity:
            parts.append(f"olgunluk>={self.min_maturity.value}")
        return ", ".join(parts) or "filtre yok"


@dataclass
class SearchQuery:
    label: str
    vector: list[float]
    filters: SearchFilters = field(default_factory=SearchFilters)
    top_k: int = 20


class Retriever(Protocol):
    def search(self, query: SearchQuery) -> list[Candidate]:
        """Benzerliğe göre azalan sırada aday döndürür; vector_score = kosinüs benzerliği."""
        ...
