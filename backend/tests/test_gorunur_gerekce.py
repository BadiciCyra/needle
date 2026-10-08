"""Görünür gerekçe (Fikir 2): yapılandırılmış iz ve kanıt doğrulama.

Birim testleri sahte embedder (HashingEmbedder) kullanır: anlam bilmez ama ortak kelime sayar.
Bu yüzden "iyi" ve "kötü" bağlar kelime ortaklığıyla kurulmuştur:
  "metin sınıflandırma" ↔ "Türkçe metin sınıflandırma"  → 2 ortak kelime, yüksek benzerlik
  "bayi"                ↔ "duygu analizi"               → ortak kelime yok, benzerlik 0
"""

from app.embeddings import HashingEmbedder
from app.graphs.match_graph import _brief_haystack, _guard_rationales, _normalize
from app.schemas import Brief, Candidate, EvidenceLink, MatchRationale, RationaleBatch
from app.seed_data import load_startups
from tests.test_match_graph import dealer_brief, run

STARTUPS = {s.id: s for s in load_startups()}
METINSEL = STARTUPS["s01"]  # Türkçe metin sınıflandırma; şikayet ve talep kategorizasyonu; duygu analizi; CRM ...
BRIEF_TEXT = _normalize("İstanbul'daki bayilerden gelen şikayetleri Türkçe metin sınıflandırma ile ayırmak istiyoruz")


def link(phrase: str, capability: str) -> EvidenceLink:
    return EvidenceLink(brief_phrase=phrase, startup_capability=capability, explanation="test")


def guard(*links: EvidenceLink, min_similarity: float = 0.35):
    batch = RationaleBatch(
        matches=[MatchRationale(startup_id="s01", fit_summary="uygun", evidence=list(links))],
        rejections=[],
    )
    return _guard_rationales(
        batch, [Candidate(startup=METINSEL)], BRIEF_TEXT, HashingEmbedder(), min_similarity
    )


# --------------------------------------------------------------------------- #
# Yardımcı fonksiyonlar
# --------------------------------------------------------------------------- #

def test_normalize_handles_turkish_capital_i():
    # Python'un kendi lower()'ı "İ" harfini "i̇" (i + birleşik nokta) yapar; bizimki düz "i" yapmalı
    assert _normalize("İzmir  ILIK\nhava") == "izmir ılık hava"


def test_brief_haystack_collects_text_and_list_fields():
    brief = Brief(title="Bayi şikayetleri", problem="Elle sınıflandırılıyor", required_capabilities=["Türkçe NLP"])
    haystack = _brief_haystack(brief.model_dump(mode="json"))
    assert "bayi şikayetleri" in haystack
    assert "elle sınıflandırılıyor" in haystack
    assert "türkçe nlp" in haystack


# --------------------------------------------------------------------------- #
# Kanıt doğrulama: üç kontrol
# --------------------------------------------------------------------------- #

def test_valid_link_is_kept_with_support_score():
    batch, kept, total = guard(link("metin sınıflandırma", "Türkçe metin sınıflandırma"))
    [evidence] = batch.matches[0].evidence
    assert (kept, total) == (1, 1)
    assert evidence.support_score is not None and evidence.support_score >= 0.35


def test_capability_not_in_profile_is_dropped():
    # 1. kontrol: Metinsel'in profilinde drone yok
    batch, kept, total = guard(link("metin sınıflandırma", "drone ile termal görüntüleme"))
    assert batch.matches[0].evidence == []
    assert (kept, total) == (0, 1)


def test_phrase_not_in_brief_is_dropped():
    # 2. kontrol: "fatura okuma" brief'te hiç geçmiyor
    batch, _, _ = guard(link("fatura okuma", "Türkçe metin sınıflandırma"))
    assert batch.matches[0].evidence == []


def test_empty_phrase_is_dropped():
    # Boş metin her metnin "içinde" sayılır; bu yüzden ayrıca kontrol ediliyor.
    # min_similarity=0: 3. kontrol kapalı, böylece testi sadece 2. kontrol geçirebilir ya da düşürebilir.
    batch, _, _ = guard(link("   ", "Türkçe metin sınıflandırma"), min_similarity=0.0)
    assert batch.matches[0].evidence == []


def test_unrelated_link_is_dropped_by_similarity():
    # 3. kontrol: ikisi de gerçek ama aralarında anlam bağı yok
    batch, _, _ = guard(link("bayi", "duygu analizi"))
    assert batch.matches[0].evidence == []


def test_turkish_capital_i_in_brief_does_not_break_phrase_check():
    # Brief "İstanbul'daki" ile başlıyor, LLM ifadeyi küçük harfle yazmış
    batch, _, _ = guard(link("istanbul'daki bayilerden gelen şikayetleri", "şikayet ve talep kategorizasyonu"),
                        min_similarity=0.0)
    assert len(batch.matches[0].evidence) == 1


def test_only_bad_links_are_removed_from_a_mixed_rationale():
    batch, kept, total = guard(
        link("metin sınıflandırma", "Türkçe metin sınıflandırma"),   # geçer
        link("metin sınıflandırma", "drone ile termal görüntüleme"),  # 1. kontrol
        link("fatura okuma", "Türkçe metin sınıflandırma"),           # 2. kontrol
        link("bayi", "duygu analizi"),                                # 3. kontrol
    )
    assert (kept, total) == (1, 4)
    assert batch.matches[0].fit_summary == "uygun"  # gerekçe kartı kalır, sadece izleri temizlenir


def test_rationale_for_startup_outside_shortlist_is_dropped():
    batch = RationaleBatch(
        matches=[MatchRationale(startup_id="s99", fit_summary="?", evidence=[])], rejections=[]
    )
    cleaned, _, _ = _guard_rationales(batch, [Candidate(startup=METINSEL)], BRIEF_TEXT, HashingEmbedder(), 0.35)
    assert cleaned.matches == []


# --------------------------------------------------------------------------- #
# Graf: yapılandırılmış iz
# --------------------------------------------------------------------------- #

def test_trace_steps_follow_the_pipeline(tmp_path):
    result = run(dealer_brief(), tmp_path)
    assert [s.stage for s in result.trace_steps] == ["plan", "retrieve", "rerank", "threshold", "evidence"]
    # eski düz metin iz ile yeni yapılandırılmış iz aynı adımları anlatır
    assert [s.message for s in result.trace_steps] == result.retrieval_trace


def test_trace_steps_carry_numbers_for_the_ui(tmp_path):
    steps = {s.stage: s for s in run(dealer_brief(), tmp_path).trace_steps}
    assert steps["plan"].queries == 3  # brief + 2 yetkinlik
    assert steps["retrieve"].round == 1
    assert steps["retrieve"].pool_size >= steps["retrieve"].new_candidates > 0
    assert steps["threshold"].shortlist_size == 5
    assert steps["evidence"].evidence_total >= steps["evidence"].evidence_kept


def test_relaxation_shows_up_as_its_own_step(tmp_path):
    result = run(dealer_brief(location_preference="Trabzon"), tmp_path)
    stages = [s.stage for s in result.trace_steps]
    assert stages[:4] == ["plan", "retrieve", "relax", "retrieve"]
    relax = result.trace_steps[2]
    assert relax.filters == "filtre yok"
    assert result.trace_steps[3].round == 2


def test_evidence_step_counts_made_up_capabilities(tmp_path):
    # Sahte LLM her aday için 1 gerçek + 1 uydurma yetkinlik yazıyor → izlerin yarısı atılmalı
    result = run(dealer_brief(), tmp_path)
    evidence = next(s for s in result.trace_steps if s.stage == "evidence")
    assert evidence.evidence_total == 2 * len(result.shortlist)
    assert evidence.evidence_kept == len(result.shortlist)
    assert all(e.support_score is not None for item in result.shortlist for e in item.rationale.evidence)


def test_strict_similarity_setting_reaches_the_graph(tmp_path):
    # Benzerlik eşiği 0,99 → hiçbir iz geçemez ama gerekçe kartları (fit_summary) yerinde kalır
    result = run(dealer_brief(), tmp_path, evidence_min_similarity=0.99)
    assert all(item.rationale.evidence == [] for item in result.shortlist)
    assert all(item.rationale.fit_summary for item in result.shortlist)
    evidence = next(s for s in result.trace_steps if s.stage == "evidence")
    assert evidence.evidence_kept == 0
