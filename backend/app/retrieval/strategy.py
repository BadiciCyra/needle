"""Dinamik RAG'in yapı taşları: çoklu sorgu, sonuç birleştirme (RRF) ve filtre gevşetme merdiveni.

Döngünün kendisi (getir → yeterli mi? → gevşet → tekrar getir) LangGraph'ta kurulur
(app/graphs/match_graph.py). Buradaki fonksiyonlar saf ve tek başına test edilebilir.
"""

from dataclasses import replace

from app.embeddings import Embedder
from app.retrieval.base import MATURITY_ORDER, Retriever, SearchFilters, SearchQuery
from app.schemas import Brief, Candidate

RRF_K = 60  # reciprocal rank fusion sabiti (literatürdeki standart değer)


def initial_filters(brief: Brief) -> SearchFilters:
    return SearchFilters(location=brief.location_preference, min_maturity=brief.min_maturity)


def build_queries(brief: Brief, embedder: Embedder, filters: SearchFilters, top_k: int) -> list[SearchQuery]:
    """Brief'in tamamı için bir sorgu + her aranan yetkinlik için ayrı birer sorgu."""
    texts = [("brief", brief.to_search_text())]
    texts += [(f"yetkinlik: {cap}", cap) for cap in brief.required_capabilities]
    vectors = embedder.embed_documents([t for _, t in texts])
    return [SearchQuery(label=label, vector=v, filters=filters, top_k=top_k) for (label, _), v in zip(texts, vectors)]


def fuse(result_lists: list[list[Candidate]]) -> list[Candidate]:
    """Reciprocal Rank Fusion: birden çok listede üst sıralarda çıkan aday öne geçer.

    Adayın vector_score'u gördüğü en yüksek kosinüs benzerliği olarak kalır; sıralama RRF'e göre yapılır.
    """
    fused: dict[str, tuple[float, Candidate]] = {}
    for results in result_lists:
        for rank, candidate in enumerate(results):
            rrf = 1.0 / (RRF_K + rank + 1)
            if candidate.startup.id in fused:
                score, best = fused[candidate.startup.id]
                if candidate.vector_score > best.vector_score:
                    best = candidate
                fused[candidate.startup.id] = (score + rrf, best)
            else:
                fused[candidate.startup.id] = (rrf, candidate)
    ordered = sorted(fused.values(), key=lambda item: item[0], reverse=True)
    return [candidate for _, candidate in ordered]


def run_queries(retriever: Retriever, queries: list[SearchQuery]) -> list[Candidate]:
    return fuse([retriever.search(q) for q in queries])


def relax(filters: SearchFilters) -> tuple[SearchFilters, str] | None:
    """Gevşetme merdiveninin bir sonraki basamağı. Gevşetilecek bir şey kalmadıysa None."""
    if filters.location:
        return replace(filters, location=None), f"lokasyon filtresi ({filters.location}) kaldırıldı"
    if filters.min_maturity:
        index = MATURITY_ORDER.index(filters.min_maturity)
        if index == 0:
            return replace(filters, min_maturity=None), "olgunluk filtresi kaldırıldı"
        lower = MATURITY_ORDER[index - 1]
        return (
            replace(filters, min_maturity=lower),
            f"olgunluk {filters.min_maturity.value} → {lower.value} seviyesine indirildi",
        )
    return None


def annotate_relaxations(candidates: list[Candidate], brief: Brief) -> list[Candidate]:
    """Kullanıcının asıl tercihini karşılamayan adaylara not düşer (negatif eşleşme gerekçesi için)."""
    for candidate in candidates:
        notes = []
        if brief.location_preference and candidate.startup.location != brief.location_preference:
            notes.append(f"lokasyon tercihi {brief.location_preference}, girişim {candidate.startup.location}")
        if brief.min_maturity:
            wanted = MATURITY_ORDER.index(brief.min_maturity)
            actual = MATURITY_ORDER.index(candidate.startup.maturity)
            if actual < wanted:
                notes.append(
                    f"beklenen olgunluk {brief.min_maturity.value}, girişim {candidate.startup.maturity.value}"
                )
        candidate.filter_notes = notes
    return candidates
