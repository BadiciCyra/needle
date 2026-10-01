"""SİSTEM 5 — Embedding (app/embeddings.py)

Ne gösterir:
  1. Gerçek çok dilli modelin yüklenmesi ve süresi
  2. Vektörün boyutu ve normalize olduğu (uzunluk = 1)
  3. Benzerlik matrisi: Türkçe eş anlamlı cümleler yakın, alakasızlar uzak
  4. İngilizce ↔ Türkçe aynı anlam (modelin çok dilli olduğu)
  5. Sahte HashingEmbedder'ın neden sadece testlik olduğu (anlam bilmez)

Çalıştırma:  python sistem_testleri/05_embedding.py
(Model bilgisayarda yoksa ilk çalıştırmada indirilir.)
"""

import math
import time

from _ortak import adim, baslik, bilgi, bitir, kontrol

from app.config import get_settings
from app.embeddings import HashingEmbedder, SentenceTransformerEmbedder, cosine

baslik("SİSTEM 5 — EMBEDDING (metin → vektör)")

adim(1, "Modeli yükle")
ayar = get_settings()
bilgi(f"model: {ayar.embedding_model}")
embedder = SentenceTransformerEmbedder(ayar.embedding_model, ayar.embedding_dim)
baslangic = time.perf_counter()
vektor = embedder.embed_query("deneme")
bilgi(f"ilk yükleme + ilk vektör: {time.perf_counter() - baslangic:.1f} sn")
baslangic = time.perf_counter()
embedder.embed_documents(["bir", "iki", "üç", "dört", "beş"] * 8)
bilgi(f"40 kısa metin (model yüklüyken): {time.perf_counter() - baslangic:.2f} sn")

adim(2, "Vektörün şekli")
uzunluk = math.sqrt(sum(x * x for x in vektor))
bilgi(f"boyut: {len(vektor)}   uzunluk: {uzunluk:.4f}   ilk 5 değer: {[round(x, 3) for x in vektor[:5]]}")
kontrol(len(vektor) == 384, "384 boyutlu vektör")
kontrol(abs(uzunluk - 1) < 1e-3, "vektör normalize (uzunluk 1) → kosinüs = iç çarpım")

adim(3, "Benzerlik matrisi")
cumleler = {
    "A": "Bayilerden gelen şikayetleri otomatik olarak kategorilere ayırmak istiyoruz",
    "B": "Müşteri geri bildirimlerini yapay zekâ ile sınıflandıran Türkçe NLP çözümü",
    "C": "Şikayet metinlerini konusuna göre gruplayan yazılım",
    "D": "Güneş paneli temizliği yapan otonom robot",
    "E": "Tarlada toprak nemini ölçen sensör",
}
for ad, metin in cumleler.items():
    bilgi(f"{ad}: {metin}")
vektorler = dict(zip(cumleler, embedder.embed_documents(list(cumleler.values()))))
bilgi("      " + "      ".join(cumleler))
for satir in cumleler:
    bilgi(f"{satir}   " + "  ".join(f"{cosine(vektorler[satir], vektorler[s]):.2f}" for s in cumleler))
kontrol(cosine(vektorler["A"], vektorler["C"]) > cosine(vektorler["A"], vektorler["D"]),
        "şikayet sınıflandırma (A) ↔ şikayet gruplama (C) > A ↔ güneş paneli (D)")
kontrol(cosine(vektorler["A"], vektorler["B"]) > cosine(vektorler["A"], vektorler["E"]),
        "A ↔ Türkçe NLP (B) > A ↔ toprak sensörü (E)")

adim(4, "Çok dillilik: aynı anlam, farklı dil")
tr, en, alakasiz = embedder.embed_documents([
    "Pompalarda arızayı önceden tahmin etmek",
    "Predicting pump failures in advance",
    "Hastane randevu hatırlatma sistemi",
])
bilgi(f"TR ↔ EN (aynı anlam): {cosine(tr, en):.2f}    TR ↔ alakasız: {cosine(tr, alakasiz):.2f}")
kontrol(cosine(tr, en) > cosine(tr, alakasiz), "Türkçe ve İngilizce aynı anlam birbirine yakın düştü")

adim(5, "Sahte embedder sadece testlik: anlam bilmez, kelime sayar")
sahte = HashingEmbedder()
a, c = sahte.embed_documents([cumleler["A"], cumleler["C"]])
bilgi(f"gerçek model A ↔ C: {cosine(vektorler['A'], vektorler['C']):.2f}    sahte A ↔ C: {cosine(a, c):.2f}")
bilgi("sahte embedder ortak kelime olmadığı için eş anlamlı cümleleri yakın bulamaz")
kontrol(cosine(a, c) < cosine(vektorler["A"], vektorler["C"]), "gerçek model anlamı sahteden daha iyi yakalıyor")

bitir()
