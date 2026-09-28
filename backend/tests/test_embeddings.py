import os

import pytest

from app.embeddings import HashingEmbedder, SentenceTransformerEmbedder, cosine


def test_hashing_embedder_is_deterministic_and_normalized():
    embedder = HashingEmbedder(dim=64)
    a = embedder.embed_query("şikayet sınıflandırma")
    assert a == embedder.embed_query("şikayet sınıflandırma")
    assert abs(sum(x * x for x in a) - 1.0) < 1e-9


def test_hashing_embedder_ranks_overlapping_text_higher():
    embedder = HashingEmbedder()
    query = embedder.embed_query("bayi şikayet metinlerini sınıflandırma")
    close = embedder.embed_query("şikayet metinlerini otomatik sınıflandırma")
    far = embedder.embed_query("güneş paneli bakım robotu")
    assert cosine(query, close) > cosine(query, far)


@pytest.mark.skipif(os.getenv("NEEDLE_REAL_MODELS") != "1", reason="Gerçek model testi: NEEDLE_REAL_MODELS=1")
def test_real_multilingual_model_understands_turkish_paraphrase():
    embedder = SentenceTransformerEmbedder("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2", 384)
    query = embedder.embed_query("Bayilerden gelen şikayetleri otomatik olarak kategorilere ayırmak istiyoruz")
    related = embedder.embed_query("Müşteri geri bildirimlerini yapay zekâ ile sınıflandıran Türkçe NLP çözümü")
    unrelated = embedder.embed_query("Güneş paneli temizliği yapan otonom robot")
    assert len(query) == 384
    assert cosine(query, related) > cosine(query, unrelated)
