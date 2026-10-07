"""Adım 2: brief → gerekçeli eşleştirme (dinamik RAG döngüsü).

Akış:
    plan_queries → retrieve → assess ─┬─ relax → retrieve   (yetersiz aday + gevşetilecek filtre varsa)
                                      └─ rerank → explain → assemble → END

- retrieve: brief + her yetkinlik için ayrı sorgu, sonuçlar RRF ile birleşir, turlar arasında havuz büyür.
- assess: havuz yeterli mi (min_candidates)? değilse filtre gevşetilir (lokasyon → olgunluk).
- rerank: çok dilli cross-encoder (ya da LLM) ile yeniden sıralama; kısa liste + "yakın ama değil" seçimi.
- explain: LLM gerekçe yazar; profilde olmayan yetkinliğe dayanan gerekçe izleri atılır.
"""

import json
from typing import TypedDict

from langgraph.graph import END, StateGraph

from app.config import Settings, get_settings
from app.embeddings import Embedder
from app.llm.client import StructuredLLM
from app.prompts import match as prompts
from app.rerank.rerankers import Reranker
from app.retrieval.base import Retriever, SearchFilters, SearchQuery
from app.retrieval.strategy import annotate_relaxations, build_queries, initial_filters, relax, run_queries
from app.schemas import (
    Brief,
    Candidate,
    MatchRationale,
    MatchResult,
    MatchResultItem,
    RationaleBatch,
    RejectionRationale,
)


PREFERENCE_PENALTY = 0.85  # lokasyon / olgunluk tercihi dışındaki adayın skor çarpanı


class MatchState(TypedDict, total=False):
    brief: dict
    filters: SearchFilters
    queries: list[SearchQuery]
    pool: dict[str, Candidate]        # startup_id → en iyi aday (turlar arasında birikir)
    round: int
    trace: list[str]
    shortlist: list[Candidate]
    rejected: list[Candidate]
    rationales: RationaleBatch
    result: MatchResult


def _describe(candidate: Candidate) -> str:
    s = candidate.startup
    lines = [
        f"[{s.id}] {s.name} — {s.sector}, {s.location}, olgunluk: {s.maturity.value}",
        f"Açıklama: {s.description}",
        "Yetkinlikler: " + " | ".join(s.capabilities),
    ]
    if candidate.filter_notes:
        lines.append("Filtre notu: " + "; ".join(candidate.filter_notes))
    return "\n".join(lines)


def _guard_rationales(batch: RationaleBatch, shortlist: list[Candidate]) -> RationaleBatch:
    """Profilde olmayan yetkinliğe dayanan gerekçe izlerini atar (uydurma gerekçe koruması)."""
    capabilities = {c.startup.id: {cap.lower() for cap in c.startup.capabilities} for c in shortlist}
    cleaned = []
    for rationale in batch.matches:
        allowed = capabilities.get(rationale.startup_id)
        if allowed is None:
            continue
        rationale.evidence = [e for e in rationale.evidence if e.startup_capability.lower() in allowed]
        cleaned.append(rationale)
    batch.matches = cleaned
    return batch


def _or(value: float | None, default: float) -> float:
    return default if value is None else value


def select_shortlist(
    ranked: list[Candidate], min_score: float, ratio: float, max_size: int, rejected_size: int
) -> tuple[list[Candidate], list[Candidate], str]:
    """Güven eşiği: kısa listeyi sabit sayıyla değil kaliteyle keser.

    1. Taban: en iyi adayın skoru min_score'un altındaysa kısa liste boştur ("uygun girişim yok").
    2. Kırpma: en iyinin skorunun en az `ratio` katını alan adaylar kısa listeye girer (en fazla max_size).
    0. Doğrudan çözüm: sıralayıcı "problemi doğrudan çözmüyor" dediği adayı (direct_fit=False) skoru ne
       olursa olsun kısa listeye almaz; taban ve oran kalan adaylara uygulanır.
    Kısa listeye giremeyen en yakın adaylar "yakındı ama" listesine geçer; kısa liste boşken de LLM
    onlar için "yakındı ama X eksik" gerekçesi yazar. Saf fonksiyon: grafı çalıştırmadan test edilebilir.
    """
    if not ranked:
        return [], [], "Güven eşiği: hiç aday yok → uygun girişim yok"

    eligible = [c for c in ranked if c.direct_fit is not False]
    indirect = len(ranked) - len(eligible)
    indirect_note = f" ({indirect} aday problemi doğrudan çözmüyor)" if indirect else ""
    if not eligible:
        return [], ranked[:rejected_size], f"Güven eşiği: doğrudan çözen aday yok{indirect_note} → uygun girişim yok"

    top = eligible[0].rerank_score or 0.0
    if top < min_score:
        note = f"Güven eşiği: en iyi skor {top:.3f} < taban {min_score}{indirect_note} → uygun girişim yok"
        return [], ranked[:rejected_size], note

    limit = ratio * top
    shortlist = [c for c in eligible[:max_size] if (c.rerank_score or 0.0) >= limit]
    chosen = {id(c) for c in shortlist}
    rejected = [c for c in ranked if id(c) not in chosen][:rejected_size]
    note = f"Güven eşiği: sınır {limit:.3f} (= {ratio} × {top:.3f}){indirect_note} → {len(shortlist)} kısa liste"
    return shortlist, rejected, note


def build_match_graph(
    retriever: Retriever,
    embedder: Embedder,
    reranker: Reranker,
    llm: StructuredLLM,
    settings: Settings | None = None,
):
    settings = settings or get_settings()

    def plan_queries(state: MatchState) -> MatchState:
        brief = Brief.model_validate(state["brief"])
        filters = initial_filters(brief)
        queries = build_queries(brief, embedder, filters, settings.retrieve_top_k)
        trace = [f"Plan: {len(queries)} sorgu (brief + {len(queries) - 1} yetkinlik), filtreler: {filters.describe()}"]
        return {"filters": filters, "queries": queries, "pool": {}, "round": 0, "trace": trace}

    def retrieve(state: MatchState) -> MatchState:
        queries = [
            SearchQuery(label=q.label, vector=q.vector, filters=state["filters"], top_k=q.top_k)
            for q in state["queries"]
        ]
        pool = dict(state["pool"])
        new = 0
        for candidate in run_queries(retriever, queries):
            existing = pool.get(candidate.startup.id)
            if existing is None:
                new += 1
                pool[candidate.startup.id] = candidate
            elif candidate.vector_score > existing.vector_score:
                pool[candidate.startup.id] = candidate
        round_no = state["round"] + 1
        trace = state["trace"] + [
            f"Tur {round_no}: filtreler ({state['filters'].describe()}) → {new} yeni aday, havuz {len(pool)}"
        ]
        return {"pool": pool, "round": round_no, "trace": trace}

    def route_after_retrieve(state: MatchState) -> str:
        enough = len(state["pool"]) >= settings.min_candidates
        if enough or state["round"] >= settings.max_retrieval_rounds or relax(state["filters"]) is None:
            return "rerank"
        return "relax"

    def relax_filters(state: MatchState) -> MatchState:
        new_filters, note = relax(state["filters"])
        return {"filters": new_filters, "trace": state["trace"] + [f"Yetersiz aday → {note}"]}

    def rerank(state: MatchState) -> MatchState:
        brief = Brief.model_validate(state["brief"])
        pool = sorted(state["pool"].values(), key=lambda c: c.vector_score, reverse=True)
        pool = annotate_relaxations(pool[: settings.retrieve_top_k], brief)
        ranked = reranker.rerank(brief.to_search_text(), pool)

        # Lokasyon / olgunluk tercihleri yumuşak cezadır: alakalı ama tercih dışı aday yine üst sıraya çıkabilir,
        # yalnızca skoru düşürülür ve notu sonuçta görünür. Alaka düzeyi tercihin önüne geçer.
        for candidate in ranked:
            candidate.raw_rerank_score = candidate.rerank_score  # ham skor, ceza öncesi (kalibrasyon için saklanır)
            if candidate.filter_notes:
                candidate.rerank_score = (candidate.rerank_score or 0.0) * PREFERENCE_PENALTY
        ranked.sort(key=lambda c: c.rerank_score or 0.0, reverse=True)

        shortlist, rejected, threshold_note = select_shortlist(
            ranked,
            # Skor ölçeği sıralayıcıya göre değişir; ayar verilmediyse sıralayıcının kendi eşiği kullanılır
            min_score=_or(settings.shortlist_min_score, reranker.min_score),
            ratio=_or(settings.shortlist_relative_ratio, reranker.relative_ratio),
            max_size=settings.shortlist_size,
            rejected_size=settings.rejected_size,
        )
        trace = state["trace"] + [
            f"Yeniden sıralama ({reranker.name}): {len(ranked)} aday → {len(shortlist)} kısa liste, {len(rejected)} elenen",
            threshold_note,
        ]
        return {"shortlist": shortlist, "rejected": rejected, "trace": trace}

    def explain(state: MatchState) -> MatchState:
        batch = llm.invoke(
            RationaleBatch,
            system=prompts.RATIONALE_SYSTEM,
            user=prompts.RATIONALE_USER.format(
                brief_json=json.dumps(state["brief"], ensure_ascii=False),
                shortlist="\n\n".join(_describe(c) for c in state["shortlist"]) or "(yok)",
                rejected="\n\n".join(_describe(c) for c in state["rejected"]) or "(yok)",
            ),
        )
        return {"rationales": _guard_rationales(batch, state["shortlist"])}

    def assemble(state: MatchState) -> MatchState:
        matches = {r.startup_id: r for r in state["rationales"].matches}
        rejections = {r.startup_id: r for r in state["rationales"].rejections}

        def item(rank: int, c: Candidate, rejected: bool) -> MatchResultItem:
            score = c.rerank_score if c.rerank_score is not None else c.vector_score
            if rejected:
                rejection = rejections.get(c.startup.id) or RejectionRationale(
                    startup_id=c.startup.id,
                    near_miss_reason="Yakındı ama kısa listedeki adaylar daha yüksek puan aldı.",
                )
                return MatchResultItem(
                    rank=rank,
                    startup=c.startup,
                    score=score,
                    vector_score=c.vector_score,
                    rerank_score=c.raw_rerank_score,
                    rejection=rejection,
                    filter_notes=c.filter_notes,
                )
            rationale = matches.get(c.startup.id) or MatchRationale(
                startup_id=c.startup.id, fit_summary="Gerekçe üretilemedi.", evidence=[]
            )
            return MatchResultItem(
                rank=rank,
                startup=c.startup,
                score=score,
                vector_score=c.vector_score,
                rerank_score=c.raw_rerank_score,
                rationale=rationale,
                filter_notes=c.filter_notes,
            )

        result = MatchResult(
            shortlist=[item(i + 1, c, False) for i, c in enumerate(state["shortlist"])],
            rejected=[item(i + 1, c, True) for i, c in enumerate(state["rejected"])],
            no_match=not state["shortlist"],
            retrieval_trace=state["trace"],
        )
        return {"result": result}

    graph = StateGraph(MatchState)
    graph.add_node("plan_queries", plan_queries)
    graph.add_node("retrieve", retrieve)
    graph.add_node("relax", relax_filters)
    graph.add_node("rerank", rerank)
    graph.add_node("explain", explain)
    graph.add_node("assemble", assemble)

    graph.set_entry_point("plan_queries")
    graph.add_edge("plan_queries", "retrieve")
    graph.add_conditional_edges("retrieve", route_after_retrieve, {"relax": "relax", "rerank": "rerank"})
    graph.add_edge("relax", "retrieve")
    graph.add_edge("rerank", "explain")
    graph.add_edge("explain", "assemble")
    graph.add_edge("assemble", END)
    return graph.compile()
