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


#Üç tasarım kararı ve gereçkeleri;


#1.Neden ayrı bir fonksiyon? Kural rerank düğümünün içine de yazılabilirdi. Ayrı bir
#fonksiyon olunca tüm grafı, LLM'i ve embedder'ı çalıştırmadan, sadece birkaç sayıyla test
#edebiliyoruz. Yan etkisi olmayan bu tür fonksiyonlara saf fonksiyon (pure function) deniyor:
#aynı girdiye her zaman aynı çıktıyı veriyor. Projede strategy.py'deki fonksiyonlar da böyle yazılmış.

#2."Yakındı ama" listesi neden değişti? Eskiden her zaman 6., 7. ve 8. sıradakiler oluyordu.
#Şimdi kısa listeye giremeyen en yakın adaylar oluyor. n01'de kırpılan 2., 3. ve 4. adaylar.
#Program yöneticisi için "neden bunlar listede değil" sorusu asıl bu adaylar için anlamlı.

#3."Uygun yok" durumunda elenenler neden dolu? Kısa liste boş olsa bile en yakın 3 aday
#"yakındı ama" listesine geçiyor. Böylece LLM her biri için "yakındı ama X yetkinliği yok"
#gerekçesini yazıyor. Bir sonraki fikirdeki eksik yetkinlik raporu bu gerekçelerden beslenecek.


def select_shortlist(
    ranked: list[Candidate], min_score: float, ratio: float, max_size: int, rejected_size: int
) -> tuple[list[Candidate], list[Candidate], str]:
    """Güven eşiği: kısa listeyi sabit sayıyla değil kaliteyle keser.

    1. Taban: en iyi adayın skoru min_score'un altındaysa kısa liste boştur ("uygun girişim yok").
    2. Kırpma: en iyinin skorunun en az `ratio` katını alan adaylar kısa listeye girer (en fazla max_size).
    Kısa listeye giremeyen en yakın adaylar "yakındı ama" listesine geçer.
    """
    if not ranked:
        return [], [], "Güven eşiği: hiç aday yok → uygun girişim yok"

    top = ranked[0].rerank_score or 0.0
    if top < min_score:
        note = f"Güven eşiği: en iyi skor {top:.3f} < taban {min_score} → uygun girişim yok"
        return [], ranked[:rejected_size], note

    limit = ratio * top
    shortlist = [c for c in ranked[:max_size] if (c.rerank_score or 0.0) >= limit]
    rejected = ranked[len(shortlist) : len(shortlist) + rejected_size]
    note = f"Güven eşiği: sınır {limit:.3f} (= {ratio} × {top:.3f}) → {len(shortlist)} kısa liste"
    return shortlist, rejected, note

#üstteki satırın açıklamaları 

#ranked == Reranker'ın skora göre büyükten küçüğe sıraladığı adaylar
#-> tuple[...]  ==  Fonksiyon üç şey döndürüyor: kısa liste, elenenler ve ize yazılacak bir not
#if not ranked:	    Hiç aday yoksa (ör. filtreler her şeyi elediyse) çökmemek için. Bu kontrol olmasaydı bir sonraki satırdaki ranked[0] hata verirdi
#top = ranked[0].rerank_score   ==  Birincinin skoru. Liste sıralı olduğu için en yüksek skor her zaman ilk elemanda
#or 0.0     ==   Skor None ise 0 kabul et. Skor tipi float | None olduğu için bu bir güvenlik önlemi
#if top < min_score:	Taban kontrolü. Birinci bile zayıfsa kısa liste boş kalır, en yakın 3 aday "yakındı ama" listesine gider
#limit = ratio * top    ==  Göreli sınır. n01 için 0,3 × 0,143 = 0,043
#[c for c in ranked[:max_size] if ...]  ==  İlk 5'in içinden sınırı geçenler. Bu yazım biçimine list comprehension deniyor: "şu listedeki her c için, koşul doğruysa yeni listeye al"
#ranked[len(shortlist) : len(shortlist) + rejected_size]    ==	Kısa listenin hemen arkasından gelen 3 aday. Kısa listede 1 aday varsa 2., 3. ve 4. sıradakiler oluyor
#


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
            #Sıra önemli: Bu satır cezadan önce olmalı. Sonra olursa cezalı skoru kopyalamış oluruz ve düzeltmek istediğimiz hatayı tekrar etmiş oluruz.
            if candidate.filter_notes:
                candidate.rerank_score = (candidate.rerank_score or 0.0) * PREFERENCE_PENALTY
        ranked.sort(key=lambda c: c.rerank_score or 0.0, reverse=True)

#Ne değişti: Sabit [:5] kesimi gitti. Yerine yeni fonksiyon çağrılıyor ve Adım 2'de eklediğin iki
#ayar settings üzerinden fonksiyona veriliyor. Düğmeler motora burada bağlanıyor. İze de yeni
#bir satır ekleniyor. Böylece her eşleştirmede eşiğin ne olduğu ve kaç adayın geçtiği kayıt altında kalıyor.


        shortlist, rejected, threshold_note = select_shortlist(
            ranked,
            min_score=settings.shortlist_min_score,
            ratio=settings.shortlist_relative_ratio,
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
