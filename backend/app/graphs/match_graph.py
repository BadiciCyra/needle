"""Adım 2: brief → gerekçeli eşleştirme (dinamik RAG döngüsü).

Akış:
    plan_queries → retrieve → assess ─┬─ relax → retrieve   (yetersiz aday + gevşetilecek filtre varsa)
                                      └─ rerank → explain → assemble → END

- retrieve: brief + her yetkinlik için ayrı sorgu, sonuçlar RRF ile birleşir, turlar arasında havuz büyür.
- assess: havuz yeterli mi (min_candidates)? değilse filtre gevşetilir (lokasyon → olgunluk).
- rerank: çok dilli cross-encoder (ya da LLM) ile yeniden sıralama; kısa liste + "yakın ama değil" seçimi.
- explain: LLM gerekçe yazar; her gerekçe izi üç kontrolden geçer (bkz. _guard_rationales).

Her düğüm ize hem düz metin (retrieval_trace) hem yapılandırılmış adım (trace_steps) yazar.
"""

import json
from typing import TypedDict

from langgraph.graph import END, StateGraph

from app.config import Settings, get_settings
from app.embeddings import Embedder, cosine
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
    TraceStep,
)


PREFERENCE_PENALTY = 0.85


class MatchState(TypedDict, total=False):
    brief: dict
    filters: SearchFilters
    queries: list[SearchQuery]
    pool: dict[str, Candidate]
    round: int
    trace: list[str]
    steps: list[dict]
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


def _log(state: MatchState, stage: str, message: str, **fields) -> dict:
    """İze bir adım ekler: hem düz metin satırı (trace) hem yapılandırılmış adım (steps); ikisi hiç ayrışmaz."""
    step = TraceStep(stage=stage, message=message, **fields)
    return {
        "trace": state.get("trace", []) + [message],
        "steps": state.get("steps", []) + [step.model_dump(exclude_none=True)],
    }


def _normalize(text: str) -> str:
    """Türkçe uyumlu küçük harf + boşluk sadeleştirme ("İ".lower() Python'da "i̇" verir, "i" değil)."""
    text = text.replace("İ", "i").replace("I", "ı").lower()
    return " ".join(text.split())


def _brief_haystack(brief: dict) -> str:
    """Brief'teki bütün metin alanlarını tek metinde toplar; brief_phrase bunun içinde aranır."""
    parts = []
    for value in brief.values():
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, list):
            parts.extend(v for v in value if isinstance(v, str))
    return _normalize(" \n ".join(parts))


def _guard_rationales(
    batch: RationaleBatch, shortlist: list[Candidate], brief_text: str, embedder: Embedder, min_similarity: float
) -> tuple[RationaleBatch, int, int]:
    """Dayanaksız gerekçe izlerini atar. Bir iz üç kontrolün üçünü de geçmeli:

    1. startup_capability girişimin profilinde birebir var mı   (uydurma yetkinlik)
    2. brief_phrase brief metninde gerçekten geçiyor mu        (uydurma ifade)
    3. ifade ile yetkinlik anlamca yeterince yakın mı           (alakasız bağ)
    Ucuz kontroller önce, model çağrısı en son. Gerekçe kartı (fit_summary) izleri boşalsa bile kalır.
    Dönüş: (temizlenmiş batch, kalan iz, toplam iz).
    """
    capabilities = {c.startup.id: {_normalize(cap) for cap in c.startup.capabilities} for c in shortlist}
    cleaned = []
    kept = total = 0
    for rationale in batch.matches:
        allowed = capabilities.get(rationale.startup_id)
        if allowed is None:
            continue
        good = []
        for e in rationale.evidence:
            total += 1
            if _normalize(e.startup_capability) not in allowed:
                continue
            phrase = _normalize(e.brief_phrase)
            if not phrase or phrase not in brief_text:
                continue
            phrase_vec, cap_vec = embedder.embed_documents([e.brief_phrase, e.startup_capability])
            score = cosine(phrase_vec, cap_vec)
            if score < min_similarity:
                continue
            e.support_score = round(score, 3)
            good.append(e)
        rationale.evidence = good
        kept += len(good)
        cleaned.append(rationale)
    batch.matches = cleaned
    return batch, kept, total


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
        message = f"Plan: {len(queries)} sorgu (brief + {len(queries) - 1} yetkinlik), filtreler: {filters.describe()}"
        log = _log({}, "plan", message, queries=len(queries), filters=filters.describe())
        return {"filters": filters, "queries": queries, "pool": {}, "round": 0, **log}

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
        message = f"Tur {round_no}: filtreler ({state['filters'].describe()}) → {new} yeni aday, havuz {len(pool)}"
        log = _log(
            state, "retrieve", message,
            round=round_no, filters=state["filters"].describe(), new_candidates=new, pool_size=len(pool),
        )
        return {"pool": pool, "round": round_no, **log}

    def route_after_retrieve(state: MatchState) -> str:
        enough = len(state["pool"]) >= settings.min_candidates
        if enough or state["round"] >= settings.max_retrieval_rounds or relax(state["filters"]) is None:
            return "rerank"
        return "relax"

    def relax_filters(state: MatchState) -> MatchState:
        new_filters, note = relax(state["filters"])
        log = _log(state, "relax", f"Yetersiz aday → {note}", filters=new_filters.describe())
        return {"filters": new_filters, **log}

    def rerank(state: MatchState) -> MatchState:
        brief = Brief.model_validate(state["brief"])
        pool = sorted(state["pool"].values(), key=lambda c: c.vector_score, reverse=True)
        pool = annotate_relaxations(pool[: settings.retrieve_top_k], brief)
        ranked = reranker.rerank(brief.to_search_text(), pool)

        for candidate in ranked:
            candidate.raw_rerank_score = candidate.rerank_score
            if candidate.filter_notes:
                candidate.rerank_score = (candidate.rerank_score or 0.0) * PREFERENCE_PENALTY
        ranked.sort(key=lambda c: c.rerank_score or 0.0, reverse=True)

        shortlist, rejected, threshold_note = select_shortlist(
            ranked,
            min_score=_or(settings.shortlist_min_score, reranker.min_score),
            ratio=_or(settings.shortlist_relative_ratio, reranker.relative_ratio),
            max_size=settings.shortlist_size,
            rejected_size=settings.rejected_size,
        )
        log = _log(
            state, "rerank",
            f"Yeniden sıralama ({reranker.name}): {len(ranked)} aday → {len(shortlist)} kısa liste, {len(rejected)} elenen",
            candidates=len(ranked),
        )
        indirect = sum(c.direct_fit is False for c in ranked)
        log = _log(
            {**state, **log}, "threshold", threshold_note,
            indirect=indirect or None, shortlist_size=len(shortlist), rejected_size=len(rejected),
        )
        return {"shortlist": shortlist, "rejected": rejected, **log}

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
        guarded, kept, total = _guard_rationales(
            batch,
            state["shortlist"],
            brief_text=_brief_haystack(state["brief"]),
            embedder=embedder,
            min_similarity=settings.evidence_min_similarity,
        )
        log = _log(
            state, "evidence",
            f"Gerekçe doğrulama: {total} izden {kept} tanesi geçti (benzerlik eşiği {settings.evidence_min_similarity})",
            evidence_kept=kept, evidence_total=total,
        )
        return {"rationales": guarded, **log}

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
            trace_steps=[TraceStep(**step) for step in state["steps"]],
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
