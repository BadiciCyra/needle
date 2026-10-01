# Sistem test script'leri

Needle'ın her parçasını **tek başına** çalıştırıp ne yaptığını adım adım ekrana yazan script'ler.
`tests/` klasöründeki pytest testlerinden farkı: bunlar öğrenmek ve denetlemek için; her adımda girdiyi,
çıktıyı ve ara durumu gösterir. Her kontrol ✓ / ✗ olarak yazılır; biri başarısızsa script 1 koduyla biter.

Komutlar `backend` klasöründen çalıştırılır.

| Script | Sistem | Gereken | Ne gösterir |
|---|---|---|---|
| `01_ayarlar.py` | `app/config.py` | — | Ayarların kaynağı, ortam değişkeni önceliği, geçersiz değerin reddi, önbellek |
| `02_semalar.py` | `app/schemas.py` | — | Eksik alanların kodla hesabı, arama metni, LLM'e giden JSON şeması, hatalı verinin reddi |
| `03_llm.py` | `app/llm/` | — (`--gercek`: OmniRoute) | Modele giden mesajlar, JSON temizliği, yeniden deneme, pes etme, kaydet/oynat |
| `04_veritabani.py` | `app/db/` | Docker + seed | Tablolar, satır sayıları, vektörler, pgvector SQL'i (sadece okur) |
| `05_embedding.py` | `app/embeddings.py` | model (yerel) | Vektörün şekli, benzerlik matrisi, çok dillilik, sahte embedder'ın sınırı |
| `06_retrieval.py` | `app/retrieval/` | model (yerel) | Çoklu sorgu, RRF puanları, filtreler, gevşetme merdiveni, notlar |
| `07_reranker.py` | `app/rerank/` | model (yerel) | Skorun oluşumu, 20 ihtiyaçta vektör / çok dilli / İngilizce reranker karşılaştırması |
| `08_brief_akisi.py` | `app/graphs/brief_graph.py` | — (`--gercek`) | Düğüm düğüm akış, takip soruları, cevap birleştirme, tek tur sınırı |
| `09_eslestirme_akisi.py` | `app/graphs/match_graph.py` | model (`--gercek`) | Dinamik RAG turları, gevşetme, yumuşak ceza, uydurma koruması, skorlar |
| `10_api.py` | `app/api/` | Docker + seed (`--gercek`) | Tüm HTTP akışı, durum kodları, veritabanına yazılanlar (kendi satırlarını temizler) |

```bash
python sistem_testleri/01_ayarlar.py
python sistem_testleri/calistir_hepsi.py                  # hepsi
python sistem_testleri/calistir_hepsi.py --veritabanisiz  # Docker kapalıyken
python sistem_testleri/calistir_hepsi.py --gercek         # gerçek LLM ile
```

Önkoşullar:

```bash
docker compose up -d db      # repo kökünde (04 ve 10 için)
python -m seed.seed_db       # bir kez: 40 girişimi gerçek embedding'lerle yükler
```

`--gercek` için `.env`'de `LLM_BASE_URL`, `LLM_API_KEY` (OmniRoute istemci anahtarı) ve `LLM_MODEL` dolu olmalı.
