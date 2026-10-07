"""Güven eşiği (Fikir 1): kısa liste sabit sayıyla değil kaliteyle kesilir.

Skorlar analiz/esik_analizi.py ile ölçülen gerçek reranker skorlarından alındı (ham ihtiyaç metniyle).
"""

from app.graphs.match_graph import select_shortlist
from app.rerank.rerankers import LLMReranker
from app.schemas import Candidate
from app.seed_data import load_startups

STARTUPS = load_startups()
MIN_SCORE = 0.003
RATIO = 0.3


def ranked(*scores: float) -> list[Candidate]:
    """Verilen skorlarla, büyükten küçüğe sıralı sahte aday listesi kurar."""
    return [Candidate(startup=STARTUPS[i], rerank_score=score) for i, score in enumerate(scores)]


def select(candidates: list[Candidate]):
    return select_shortlist(candidates, min_score=MIN_SCORE, ratio=RATIO, max_size=5, rejected_size=3)


def ids(candidates: list[Candidate]) -> list[str]:
    return [c.startup.id for c in candidates]


def test_clear_winner_is_shown_alone():
    # n01 (bayi şikayeti): birinci açık ara önde, diğerleri alakasız
    candidates = ranked(0.143, 0.001, 0.0, 0.0, 0.0, 0.0)
    shortlist, rejected, note = select(candidates)
    assert ids(shortlist) == ids(candidates[:1])
    # kırpılan en yakın adaylar "yakındı ama" listesine geçer
    assert ids(rejected) == ids(candidates[1:4])
    assert "1 kısa liste" in note


def test_close_runner_up_stays_in_shortlist():
    # n08: ikinci aday birincinin %56'sını almış → sınır 0,3 × 0,018 = 0,0054'ü geçer
    shortlist, _, _ = select(ranked(0.018, 0.010, 0.004, 0.001, 0.001))
    assert len(shortlist) == 2


def test_weak_top_score_means_no_suitable_startup():
    # n11: herkes eşit derecede kötü → göreli kural hepsini tutardı, taban yakalar
    shortlist, rejected, note = select(ranked(*[0.001] * 8))
    assert shortlist == []
    assert len(rejected) == 3  # en yakın adaylar yine de "yakındı ama" gerekçesi için saklanır
    assert "uygun girişim yok" in note


def test_no_candidates_at_all():
    shortlist, rejected, note = select([])
    assert shortlist == [] and rejected == []
    assert "uygun girişim yok" in note


def test_shortlist_never_exceeds_max_size():
    # herkes eşit derecede iyi olsa bile en fazla 5 aday gösterilir
    shortlist, rejected, _ = select(ranked(*[0.9] * 10))
    assert len(shortlist) == 5
    assert len(rejected) == 3


def test_score_exactly_on_the_limit_is_kept():
    # sınır = 0,3 × 0,5 = 0,15 → tam sınırdaki aday kalır (≥), hemen altındaki atılır
    shortlist, _, _ = select(ranked(0.5, 0.15, 0.149))
    assert len(shortlist) == 2


def test_llm_reranker_thresholds_trim_weak_tail():
    # Kayıtlı "kullanıcı geri bildirim platformu" brief'inin LLM puanları (onda bir): 9, 7, 5, 4, 3
    llm = LLMReranker(llm=None)
    shortlist, rejected, _ = select_shortlist(
        ranked(0.9, 0.7, 0.5, 0.4, 0.3, 0.3), llm.min_score, llm.relative_ratio, max_size=5, rejected_size=3
    )
    assert len(shortlist) == 2 and len(rejected) == 3


def test_llm_reranker_reports_no_match_when_best_is_weak():
    llm = LLMReranker(llm=None)
    shortlist, rejected, _ = select_shortlist(
        ranked(0.4, 0.3, 0.2, 0.1), llm.min_score, llm.relative_ratio, max_size=5, rejected_size=3
    )
    assert shortlist == [] and len(rejected) == 3


def test_indirect_candidates_never_enter_shortlist_even_with_high_scores():
    # Su kaçağı örneği: teğet adaylar 9/10 alsa da "doğrudan çözmüyor" dendiyse kısa listeye girmez
    candidates = ranked(0.9, 0.9, 0.8, 0.7)
    for c, direct in zip(candidates, (False, True, False, True)):
        c.direct_fit = direct
    shortlist, rejected, note = select(candidates)
    assert ids(shortlist) == ids([candidates[1], candidates[3]])
    assert ids(rejected) == ids([candidates[0], candidates[2]])  # en yakın teğet adaylar "yakındı ama"
    assert "2 aday problemi doğrudan çözmüyor" in note


def test_no_direct_solver_means_no_match():
    candidates = ranked(0.9, 0.8, 0.8, 0.6)
    for c in candidates:
        c.direct_fit = False
    shortlist, rejected, note = select(candidates)
    assert shortlist == [] and len(rejected) == 3
    assert "doğrudan çözen aday yok" in note
