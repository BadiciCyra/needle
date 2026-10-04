"""Güven eşiği (Fikir 1): kısa liste sabit sayıyla değil kaliteyle kesilir.

Skorlar analiz/esik_analizi.py ile ölçülen gerçek reranker skorlarından alındı (ham ihtiyaç metniyle).
"""

from app.graphs.match_graph import select_shortlist
from app.schemas import Candidate
from app.seed_data import load_startups

STARTUPS = load_startups()
MIN_SCORE = 0.003
RATIO = 0.3


#ranked(0.143, 0.001, ...): Verilen skorlarla sahte bir aday listesi kuruyor. 
# Her testte Candidate(...) yazmak yerine bunu kullanıyoruz. 
# select(...): select_shortlist'i bizim eşiklerimizle (0,003 ve 0,3) çağırıyor.
#ids(...): Aday listesini id listesine çeviriyor, karşılaştırmayı kolaylaştırıyor.




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
#bu fonksiyonun girdisi n01 skorları
#beklenen 1 kısa liste sonraki 3 elenen aday
#kırpma "olabilitesi olan" adayların listesi 


def test_close_runner_up_stays_in_shortlist():
    # n08: ikinci aday birincinin %56'sını almış → sınır 0,3 × 0,018 = 0,0054'ü geçer
    shortlist, _, _ = select(ranked(0.018, 0.010, 0.004, 0.001, 0.001))
    assert len(shortlist) == 2
#bu fonksiyonun girdisi n08 skorları 
#2 kısa liste
#yakın ikinci adayın kırpılması 


def test_weak_top_score_means_no_suitable_startup():
    # n11: herkes eşit derecede kötü → göreli kural hepsini tutardı, taban yakalar
    shortlist, rejected, note = select(ranked(*[0.001] * 8))
    assert shortlist == []
    assert len(rejected) == 3  # en yakın adaylar yine de "yakındı ama" gerekçesi için saklanır
    assert "uygun girişim yok" in note
#bu fonksiyonun girdisi n011 skorları 
#ksıa liste boş 3 eleman
#taban


def test_no_candidates_at_all():
    shortlist, rejected, note = select([])
    assert shortlist == [] and rejected == []
    assert "uygun girişim yok" in note
#bu fonksiyonun girdisi boş liste
#çökmeden uygun yok 
#if not ranked: koruması sağlar 







#Aşşağıdaki son iki test sınır durumlarını (edge case) sınıyor. 
# Hatalar en çok bu noktalarda çıkar: listeboşken, liste çok uzunken, değer tam sınırdayken.
#"Normal" durumları test etmek kolay. Sağlam bir test seti uç durumları da kapsar.



def test_shortlist_never_exceeds_max_size():
    # herkes eşit derecede iyi olsa bile en fazla 5 aday gösterilir
    shortlist, rejected, _ = select(ranked(*[0.9] * 10))
    assert len(shortlist) == 5
    assert len(rejected) == 3
#bu fonksiyonun girdisi 10 tane 0,9
#tam 5 aday
#en fazla 5 sınırı



def test_score_exactly_on_the_limit_is_kept():
    # sınır = 0,3 × 0,5 = 0,15 → tam sınırdaki aday kalır (≥), hemen altındaki atılır
    shortlist, _, _ = select(ranked(0.5, 0.15, 0.149))
    assert len(shortlist) == 2
#0,5 0,15 0,149
#2 aday
#sınırdaki adayın kalması 


