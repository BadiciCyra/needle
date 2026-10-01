"""SİSTEM 7 — Reranker (app/rerank/rerankers.py)

Ne gösterir:
  1. Çok dilli cross-encoder'ın nasıl skor verdiği (logit → sigmoid → 0-1)
  2. 5 ihtiyaçta "sadece vektör" ile "vektör + reranker" sıralamasının karşılaştırması
  3. İngilizce cross-encoder ile çok dilli olanın farkı (neden TercihChatAi'dekini almadık)
  4. passthrough ve llm arka uçlarının davranışı

Çalıştırma:  python sistem_testleri/07_reranker.py
(İngilizce model bilgisayarda yoksa 3. adım atlanır.)
"""

import json
import math

from _ortak import SiraliSahteLLM, adim, baslik, bilgi, bitir, kontrol

from app.config import Settings, get_settings
from app.embeddings import SentenceTransformerEmbedder
from app.llm.client import StructuredLLM
from app.rerank.rerankers import CrossEncoderReranker, LLMReranker, PassthroughReranker
from app.retrieval.base import SearchQuery
from app.retrieval.memory import InMemoryRetriever
from app.seed_data import load_needs, load_startups

baslik("SİSTEM 7 — RERANKER (yeniden sıralama)")
ayar = get_settings()
embedder = SentenceTransformerEmbedder(ayar.embedding_model, ayar.embedding_dim)
retriever = InMemoryRetriever(load_startups(), embedder)
reranker = CrossEncoderReranker(ayar.rerank_model)
ihtiyaclar = {n["id"]: n["raw_text"] for n in load_needs()}

adim(1, "Cross-encoder skoru nasıl oluşuyor")
model = reranker._load()
metin = ihtiyaclar["n12"]
aday = next(s for s in load_startups() if s.name == "İSG Vizyon")
logit = float(model.predict([(metin, aday.to_search_text())])[0])
bilgi(f"ihtiyaç: {metin}")
bilgi(f"aday:    {aday.name}")
bilgi(f"ham çıktı (logit): {logit:.2f}  →  sigmoid: 1 / (1 + e^-logit) = {1 / (1 + math.exp(-logit)):.3f}")
kontrol(0 <= 1 / (1 + math.exp(-logit)) <= 1, "skor 0-1 aralığına çevrildi")

adim(2, "20 ihtiyaçta üç yöntemin karşılaştırması (ham ihtiyaç metniyle, brief adımı yok)")
# Her ihtiyaç için "doğru" girişim (örnek veri bu eşleşmelere göre hazırlandı)
DOGRU = {
    "n01": "s01", "n02": "s06", "n03": "s10", "n04": "s17", "n05": "s27", "n06": "s23", "n07": "s33",
    "n08": "s29", "n09": "s14", "n10": "s07", "n11": "s02", "n12": "s08", "n13": "s09", "n14": "s03",
    "n15": "s12", "n16": "s35", "n17": "s15", "n18": "s38", "n19": "s25", "n20": "s37",
}
yontemler = {"sadece vektör": None, "çok dilli reranker": reranker}
try:
    yontemler["İngilizce reranker"] = CrossEncoderReranker("cross-encoder/ms-marco-MiniLM-L-6-v2")
    yontemler["İngilizce reranker"]._load()
except Exception as hata:
    bilgi(f"İngilizce model yüklenemedi, karşılaştırmadan çıkarıldı ({type(hata).__name__})")
    yontemler.pop("İngilizce reranker", None)


def sira(hedef: str, adaylar) -> int:
    ids = [c.startup.id for c in adaylar]
    return ids.index(hedef) + 1 if hedef in ids else 99


siralar = {ad: [] for ad in yontemler}
bilgi("ihtiyaç  " + "  ".join(f"{ad:>20}" for ad in yontemler))
for nid, hedef in DOGRU.items():
    adaylar = retriever.search(SearchQuery(label="ham", vector=embedder.embed_query(ihtiyaclar[nid]), top_k=12))
    satir = []
    for ad, rr in yontemler.items():
        s = sira(hedef, adaylar if rr is None else rr.rerank(ihtiyaclar[nid], [c.model_copy() for c in adaylar]))
        siralar[ad].append(s)
        satir.append(f"{s:>20}")
    bilgi(f"{nid}      " + "  ".join(satir))

bilgi("")
for ad, s in siralar.items():
    mrr = sum(1 / x for x in s) / len(s)
    bilgi(f"{ad:<20} 1. sırada: {sum(x == 1 for x in s):>2}/20   ilk 3'te: {sum(x <= 3 for x in s):>2}/20   MRR: {mrr:.3f}")
bilgi("MRR: doğru girişimin ortalama ne kadar üstte çıktığı (1,0 = hep birinci)")
vektor_ilk = sum(x == 1 for x in siralar["sadece vektör"])
kontrol(sum(x == 1 for x in siralar["çok dilli reranker"]) > vektor_ilk,
        "çok dilli reranker doğru girişimi sadece vektör aramasından daha sık birinci yaptı")

adim(3, "Hangi reranker? (karar notu)")
if "İngilizce reranker" in siralar:
    fark = sum(x == 1 for x in siralar["İngilizce reranker"]) - sum(x == 1 for x in siralar["çok dilli reranker"])
    bilgi(f"İngilizce − çok dilli = {fark:+d} ihtiyaç (1. sırada)")
    bilgi("20 örnekte birkaç ihtiyaçlık fark istatistiksel olarak anlamlı değil; ikisi yakın.")
    bilgi("Asıl karar, gerçek LLM'in ürettiği brief'lerle yapılacak ölçümle verilmeli.")
    kontrol(True, "karşılaştırma tamamlandı (bilgi amaçlı, kazanan iddiası yok)")

adim(4, "Diğer arka uçlar")
adaylar = retriever.search(SearchQuery(label="ham", vector=embedder.embed_query(ihtiyaclar["n01"]), top_k=3))
gecis = PassthroughReranker().rerank(ihtiyaclar["n01"], adaylar)
kontrol([c.rerank_score for c in gecis] == sorted([c.vector_score for c in gecis], reverse=True),
        "passthrough: rerank skoru = vektör skoru, sıra değişmez")
puanlar = {"scores": [{"startup_id": c.startup.id, "score": 10 - 3 * i} for i, c in enumerate(reversed(adaylar))]}
llm_rr = LLMReranker(StructuredLLM(SiraliSahteLLM([json.dumps(puanlar)]), Settings(demo_mode="off")))
sirali = llm_rr.rerank(ihtiyaclar["n01"], adaylar)
bilgi("llm (sahte puanlar): " + ", ".join(f"{c.startup.name}={c.rerank_score:.1f}" for c in sirali))
kontrol(sirali[0].startup.id == adaylar[-1].startup.id, "llm: modelin verdiği 0-10 puana göre yeniden sıraladı")

bitir()
