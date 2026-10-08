import json

from app.config import Settings
from app.embeddings import HashingEmbedder
from app.graphs.match_graph import build_match_graph
from app.llm.client import StructuredLLM
from app.rerank.rerankers import PassthroughReranker
from app.retrieval.memory import InMemoryRetriever
from app.schemas import Brief, Maturity
from app.seed_data import load_startups
from tests.fakes import ScriptedBackend

EMBEDDER = HashingEmbedder()
STARTUPS = load_startups()


class EchoRationaleBackend:
    """Prompttaki id'leri okuyup her aday için gerekçe üreten sahte LLM; bir de uydurma yetkinlik ekler."""

    model_name = "fake-model"

    def complete(self, messages):
        user = messages[1]["content"]
        short, rejected = user.split("Elenenler (rejections):")
        ids = lambda text: [line[1:4] for line in text.splitlines() if line.startswith("[s")]
        by_id = {s.id: s for s in STARTUPS}
        matches = [
            {
                "startup_id": i,
                "fit_summary": f"{by_id[i].name} uygun.",
                "evidence": [
                    {"brief_phrase": "şikayet", "startup_capability": by_id[i].capabilities[0], "explanation": "örtüşüyor"},
                    {"brief_phrase": "şikayet", "startup_capability": "UYDURMA YETKİNLİK", "explanation": "yok"},
                ],
            }
            for i in ids(short)
        ]
        rejections = [{"startup_id": i, "near_miss_reason": "Yakındı ama X, çünkü Y."} for i in ids(rejected)]
        return json.dumps({"matches": matches, "rejections": rejections}, ensure_ascii=False)


def run(brief: Brief, tmp_path, **settings_overrides):
    # Sahte embedder anlam bilmez; graf testlerinde benzerlik kontrolü varsayılan olarak kapalı.
    # Kanıt doğrulamayı sınayan testler (test_gorunur_gerekce.py) bu ayarı kendileri verir.
    settings = Settings(**{"demo_cache_dir": str(tmp_path), "evidence_min_similarity": 0.0, **settings_overrides})
    graph = build_match_graph(
        retriever=InMemoryRetriever(STARTUPS, EMBEDDER),
        embedder=EMBEDDER,
        reranker=PassthroughReranker(),
        llm=StructuredLLM(EchoRationaleBackend(), settings),
        settings=settings,
    )
    return graph.invoke({"brief": brief.model_dump(mode="json")})["result"]


def dealer_brief(**overrides) -> Brief:
    data = dict(
        title="Bayi şikayetlerinin sınıflandırılması",
        problem="bayilerden gelen şikayet metinleri elle sınıflandırılıyor",
        required_capabilities=["Türkçe metin sınıflandırma", "şikayet ve talep kategorizasyonu"],
    )
    data.update(overrides)
    return Brief(**data)


def test_close_scores_keep_full_shortlist_and_three_rejected(tmp_path):
    # Sahte embedder'ın skorları birbirine yakın (0,60 · 0,33 · 0,32 · 0,30 · 0,27): sınır 0,3 × 0,60 = 0,18,
    # beşi de geçer. Güven eşiğinin kırptığı durumlar tests/test_guven_esigi.py'de.
    result = run(dealer_brief(), tmp_path)
    assert len(result.shortlist) == 5
    assert len(result.rejected) == 3
    assert result.no_match is False
    assert result.shortlist[0].startup.id == "s01"
    assert all(item.rationale for item in result.shortlist)
    assert all(item.rejection.near_miss_reason.startswith("Yakındı") for item in result.rejected)


def test_hallucinated_capabilities_are_removed_from_evidence(tmp_path):
    result = run(dealer_brief(), tmp_path)
    for item in result.shortlist:
        assert [e.startup_capability for e in item.rationale.evidence] == [item.startup.capabilities[0]]


def test_filters_are_relaxed_when_too_few_candidates(tmp_path):
    # Trabzon'da tek girişim var → lokasyon filtresi gevşetilmeli
    result = run(dealer_brief(location_preference="Trabzon"), tmp_path)
    trace = "\n".join(result.retrieval_trace)
    assert "Tur 1" in trace and "Tur 2" in trace
    assert "lokasyon filtresi (Trabzon) kaldırıldı" in trace
    assert len(result.shortlist) == 5


def test_relevance_beats_location_preference_but_note_is_shown(tmp_path):
    result = run(dealer_brief(location_preference="Trabzon"), tmp_path)
    # Trabzon'daki tek girişim (mobil form yazılımı) alakasız; İstanbul'daki NLP girişimi yine üstte,
    # ama "lokasyon tercihi dışında" notuyla
    top = result.shortlist[0]
    assert top.startup.id == "s01"
    assert any("lokasyon tercihi Trabzon" in note for note in top.filter_notes)


def test_preference_penalty_breaks_ties_in_favor_of_matching_location(tmp_path):
    istanbul = run(dealer_brief(location_preference="İstanbul"), tmp_path)
    assert all(not item.filter_notes for item in istanbul.shortlist[:1])


def test_no_relaxation_needed_when_enough_candidates(tmp_path):
    result = run(dealer_brief(min_maturity=Maturity.idea), tmp_path)
    assert not any("Yetersiz aday" in line for line in result.retrieval_trace)


def test_strict_ratio_setting_trims_the_shortlist(tmp_path):
    # Ayar grafa gerçekten bağlı mı? Oran 0,9 olunca sadece birinciye çok yakın olanlar kalır.
    result = run(dealer_brief(), tmp_path, shortlist_relative_ratio=0.9)
    assert 1 <= len(result.shortlist) < 5
    assert result.shortlist[0].startup.id == "s01"
    assert any("Güven eşiği" in line for line in result.retrieval_trace)


def test_high_min_score_setting_returns_no_match_with_near_misses(tmp_path):
    # Taban birincinin skorunun üstündeyse: kısa liste boş, en yakın 3 aday "yakındı ama" gerekçesiyle döner
    result = run(dealer_brief(), tmp_path, shortlist_min_score=0.99)
    assert result.shortlist == []
    assert result.no_match is True
    assert len(result.rejected) == 3
    assert all(item.rejection.near_miss_reason.startswith("Yakındı") for item in result.rejected)
    assert any("uygun girişim yok" in line for line in result.retrieval_trace)


def test_raw_rerank_score_is_kept_before_preference_penalty(tmp_path):
    # s01 İstanbul'da, kurum Trabzon istiyor → skoru 0,85 ile cezalandırılır; ham skor ayrıca saklanmalı
    top = run(dealer_brief(location_preference="Trabzon"), tmp_path).shortlist[0]
    assert top.filter_notes
    assert abs(top.score - top.rerank_score * 0.85) < 1e-9
