from sqlalchemy.dialects import postgresql

from app.embeddings import HashingEmbedder
from app.retrieval.base import SearchFilters, SearchQuery
from app.retrieval.memory import InMemoryRetriever
from app.retrieval.pgvector import build_statement
from app.retrieval.strategy import annotate_relaxations, build_queries, fuse, initial_filters, relax, run_queries
from app.schemas import Brief, Candidate, Maturity
from app.seed_data import load_startups

EMBEDDER = HashingEmbedder()


def dealer_brief(**overrides) -> Brief:
    data = dict(
        title="Bayi şikayetlerini sınıflandırma",
        problem="bayilerden gelen şikayet metinleri elle sınıflandırılıyor",
        required_capabilities=["Türkçe metin sınıflandırma", "şikayet ve talep kategorizasyonu"],
    )
    data.update(overrides)
    return Brief(**data)


def test_one_query_for_brief_plus_one_per_capability():
    queries = build_queries(dealer_brief(), EMBEDDER, SearchFilters(), top_k=10)
    assert [q.label for q in queries] == [
        "brief",
        "yetkinlik: Türkçe metin sınıflandırma",
        "yetkinlik: şikayet ve talep kategorizasyonu",
    ]


def test_capability_query_brings_the_nlp_startup_to_the_top():
    retriever = InMemoryRetriever(load_startups(), EMBEDDER)
    brief = dealer_brief()
    results = run_queries(retriever, build_queries(brief, EMBEDDER, initial_filters(brief), top_k=10))
    assert results[0].startup.id == "s01"


def test_fuse_rewards_candidates_found_by_several_queries(tmp_path):
    startups = load_startups()[:3]
    a, b, c = (Candidate(startup=s, vector_score=0.5) for s in startups)
    fused = fuse([[a, b], [c, b], [b]])
    assert fused[0].startup.id == b.startup.id


def test_location_filter_is_respected():
    retriever = InMemoryRetriever(load_startups(), EMBEDDER)
    query = SearchQuery(label="brief", vector=EMBEDDER.embed_query("yapay zeka"), filters=SearchFilters(location="Konya"))
    assert {c.startup.location for c in retriever.search(query)} == {"Konya"}


def test_relaxation_ladder_drops_location_then_lowers_maturity():
    filters = SearchFilters(location="Konya", min_maturity=Maturity.mvp)
    step1, note1 = relax(filters)
    assert step1.location is None and "lokasyon" in note1
    step2, note2 = relax(step1)
    assert step2.min_maturity == Maturity.prototype and "olgunluk" in note2
    step3, _ = relax(step2)
    assert step3.min_maturity == Maturity.idea
    step4, _ = relax(step3)
    assert step4.min_maturity is None
    assert relax(step4) is None


def test_relaxed_candidates_get_notes_for_negative_matching():
    brief = dealer_brief(location_preference="Ankara", min_maturity=Maturity.early_revenue)
    s01 = next(s for s in load_startups() if s.id == "s01")
    [annotated] = annotate_relaxations([Candidate(startup=s01)], brief)
    assert any("lokasyon" in n for n in annotated.filter_notes)
    assert any("olgunluk" in n for n in annotated.filter_notes)


def test_pgvector_statement_applies_filters():
    query = SearchQuery(
        label="brief",
        vector=[0.0] * 384,
        filters=SearchFilters(location="Ankara", min_maturity=Maturity.early_revenue, exclude_ids=frozenset({"s02"})),
        top_k=5,
    )
    sql = str(build_statement(query).compile(dialect=postgresql.dialect()))
    assert "<=>" in sql
    assert "startups.location" in sql
    assert "startups.maturity IN" in sql
    assert "NOT IN" in sql
