"""Bellek içi retriever: testler ve veritabanısız hızlı deneme için. pgvector ile aynı filtre anlamı."""

from app.embeddings import Embedder, cosine
from app.retrieval.base import SearchQuery, maturities_at_least
from app.schemas import Candidate, StartupProfile


class InMemoryRetriever:
    def __init__(self, startups: list[StartupProfile], embedder: Embedder):
        self.startups = startups
        self.vectors = embedder.embed_documents([s.to_search_text() for s in startups])

    def search(self, query: SearchQuery) -> list[Candidate]:
        allowed_maturities = maturities_at_least(query.filters.min_maturity)
        scored = []
        for startup, vector in zip(self.startups, self.vectors):
            if startup.id in query.filters.exclude_ids:
                continue
            if query.filters.location and startup.location != query.filters.location:
                continue
            if allowed_maturities and startup.maturity.value not in allowed_maturities:
                continue
            scored.append(Candidate(startup=startup, vector_score=cosine(query.vector, vector)))
        scored.sort(key=lambda c: c.vector_score, reverse=True)
        return scored[: query.top_k]
