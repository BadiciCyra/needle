"""Program yöneticisi raporu: eksik yetkinlik gruplaması (saf fonksiyon)."""

from app.api.report_routes import _sector_label, group_phrases
from app.embeddings import HashingEmbedder


def test_same_phrase_is_counted_once_per_need():
    groups = group_phrases(
        [("Türkçe metin sınıflandırma", "Bayi şikayeti"), ("türkçe metin  sınıflandırma", "Bayi şikayeti"),
         ("Türkçe metin sınıflandırma", "Müşteri geri bildirimi")],
        HashingEmbedder(),
    )
    [g] = groups
    assert g.needs == 2  # aynı ihtiyacın iki "yakındı ama" adayı aynı eksikliği iki kez saydırmaz
    assert g.need_titles == ["Bayi şikayeti", "Müşteri geri bildirimi"]


def test_similar_phrases_merge_and_unrelated_stay_apart():
    # Sahte embedder ortak kelime sayar: "metin sınıflandırma" ile "Türkçe metin sınıflandırma" benzer,
    # "su kaçağı tespiti" alakasız
    groups = group_phrases(
        [("Türkçe metin sınıflandırma", "A"), ("Türkçe metin sınıflandırma", "B"), ("metin sınıflandırma", "C"),
         ("su kaçağı tespiti", "D")],
        HashingEmbedder(),
        threshold=0.6,
    )
    assert [(g.capability, g.needs) for g in groups] == [("Türkçe metin sınıflandırma", 3), ("su kaçağı tespiti", 1)]
    assert groups[0].variants == ["metin sınıflandırma"]


def test_blank_phrases_are_ignored():
    assert group_phrases([("  ", "A")], HashingEmbedder()) == []


def test_sector_label_uses_turkish_capitals():
    assert _sector_label("ilaç") == "İlaç"
    assert _sector_label("ışık") == "Işık"
    assert _sector_label(None) == "Belirtilmemiş"
