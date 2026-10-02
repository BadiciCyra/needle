"""SİSTEM 9 — Eşleştirme akışı / dinamik RAG (app/graphs/match_graph.py)

Gerçek embedding + gerçek cross-encoder ile, düğüm düğüm çalıştırır. Gerekçe LLM'i varsayılan olarak
sahtedir (aday id'lerini okuyup gerekçe yazar ve bilerek UYDURMA bir yetkinlik ekler).

Ne gösterir:
  1. Senaryo A — filtresiz brief: tek tur yeterli, gevşetme yok
  2. Senaryo B — Trabzon tercihi: aday yetmez → filtre gevşetilir → ikinci tur
  3. Yumuşak ceza: alakalı ama tercih dışı aday yine üstte, notuyla
  4. Uydurma gerekçe koruması: profilde olmayan yetkinlik izden atılır
  5. Kısa liste skorları (bilinen zayıf nokta: düşük skorlu adaylar da 5'e giriyor)
  6. (--gercek) Gerekçeyi gerçek LLM yazar

Çalıştırma:  python sistem_testleri/09_eslestirme_akisi.py            (sahte gerekçe LLM'i)
             python sistem_testleri/09_eslestirme_akisi.py --gercek   (OmniRoute)
"""

import json
import tempfile
import time

from _ortak import adim, baslik, bilgi, bitir, gercek_mod, kontrol

from app.config import Settings, get_settings
from app.embeddings import SentenceTransformerEmbedder
from app.graphs.match_graph import PREFERENCE_PENALTY, build_match_graph
from app.llm.client import StructuredLLM
from app.rerank.rerankers import CrossEncoderReranker
from app.retrieval.memory import InMemoryRetriever
from app.schemas import Brief
from app.seed_data import load_startups

GIRISIMLER = {s.id: s for s in load_startups()}
UYDURMA = "kuantum bilgisayar optimizasyonu"


class GerekceYazanSahteLLM:
    """Prompttaki [sXX] id'lerini okuyup her aday için gerekçe üretir; her gerekçeye bir uydurma iz ekler."""

    model_name = "sahte-model"

    def complete(self, messages):
        user = messages[1]["content"]
        kisa, elenen = user.split("Elenenler (rejections):")
        ids = lambda metin: [s[1:4] for s in metin.splitlines() if s.startswith("[s")]
        matches = [{
            "startup_id": i, "fit_summary": f"{GIRISIMLER[i].name} ihtiyaçla örtüşüyor.",
            "evidence": [
                {"brief_phrase": "şikayetleri sınıflandırmak", "startup_capability": GIRISIMLER[i].capabilities[0],
                 "explanation": "doğrudan örtüşüyor"},
                {"brief_phrase": "şikayetleri sınıflandırmak", "startup_capability": UYDURMA,
                 "explanation": "uydurma iz (koruma bunu atmalı)"},
            ]} for i in ids(kisa)]
        rejections = [{"startup_id": i, "near_miss_reason": f"Yakındı ama {GIRISIMLER[i].name} metin analizi yapmıyor."}
                      for i in ids(elenen)]
        return json.dumps({"matches": matches, "rejections": rejections}, ensure_ascii=False)


def calistir(graf, brief: Brief):
    for olay in graf.stream({"brief": brief.model_dump(mode="json")}, stream_mode="updates"):
        for dugum, g in olay.items():
            bilgi(f"→ {dugum:<10} yazdı: {', '.join(g) if g else '-'}")
            if "result" in (g or {}):
                return g["result"]


def yazdir(sonuc) -> None:
    bilgi("RAG kaydı:")
    for satir in sonuc.retrieval_trace:
        bilgi(satir, girinti=8)
    bilgi("Kısa liste:")
    for k in sonuc.shortlist:
        bilgi(f"{k.rank}. {k.startup.name:<17} skor {k.score:.3f}  vektör {k.vector_score:.2f}  "
              f"{k.startup.location:<9} notlar: {k.filter_notes or '-'}", girinti=8)
    bilgi("Elenenler (yakın ama değil):")
    for k in sonuc.rejected:
        bilgi(f"{k.rank}. {k.startup.name:<17} skor {k.score:.3f}  → {k.rejection.near_miss_reason}", girinti=8)


baslik("SİSTEM 9 — EŞLEŞTİRME AKIŞI (dinamik RAG)")
ayar = get_settings()
embedder = SentenceTransformerEmbedder(ayar.embedding_model, ayar.embedding_dim)
reranker = CrossEncoderReranker(ayar.rerank_model)
retriever = InMemoryRetriever(load_startups(), embedder)
if gercek_mod():
    from app.llm.client import get_structured_llm
    llm = get_structured_llm()
    bilgi(f"gerekçe LLM'i: GERÇEK ({ayar.llm_model})")
else:
    llm = StructuredLLM(GerekceYazanSahteLLM(), Settings(demo_mode="off", demo_cache_dir=tempfile.mkdtemp()))
    bilgi("gerekçe LLM'i: sahte (gerçek için --gercek)")
graf = build_match_graph(retriever, embedder, reranker, llm, ayar)

brief = Brief(
    title="Bayi şikayetlerinin otomatik sınıflandırılması",
    problem="Bayilerden gelen şikayet metinleri elle okunup sınıflandırılıyor, çok yavaş",
    scope="Ayda yaklaşık 3.000 şikayet, bayi portalı ve e-posta",
    required_capabilities=["Türkçe metin sınıflandırma", "şikayet ve talep kategorizasyonu"],
    success_criteria="%85 doğru kategori", timeline="3 ay",
)

adim("A", "Filtresiz brief")
t = time.perf_counter()
a = calistir(graf, brief)
bilgi(f"süre: {time.perf_counter() - t:.1f} sn")
yazdir(a)
kontrol(len(a.shortlist) == 5 and len(a.rejected) == 3, "5 kısa liste + 3 elenen")
kontrol(a.shortlist[0].startup.name == "Metinsel", "1. sırada Metinsel")
kontrol(not any("Yetersiz aday" in s for s in a.retrieval_trace), "havuz yeterli, filtre gevşetilmedi")

adim("B", "Trabzon tercihi → gevşetme")
b = calistir(graf, brief.model_copy(update={"location_preference": "Trabzon"}))
yazdir(b)
kontrol(any("lokasyon filtresi (Trabzon) kaldırıldı" in s for s in b.retrieval_trace), "lokasyon filtresi gevşetildi")
kontrol(sum(s.startswith("Tur") for s in b.retrieval_trace) == 2, "iki arama turu yapıldı")

adim("C", f"Yumuşak ceza (tercih dışı aday skoru × {PREFERENCE_PENALTY})")
ilk = b.shortlist[0]
bilgi(f"1. sıra: {ilk.startup.name} ({ilk.startup.location}) notu: {ilk.filter_notes}")
kontrol(ilk.startup.name == "Metinsel", "alaka, lokasyon tercihinin önüne geçti")
kontrol(any("lokasyon tercihi Trabzon" in n for n in ilk.filter_notes), "tercih dışı olduğu notla belirtildi")

adim("D", "Uydurma gerekçe koruması")
izler = [e.startup_capability for k in a.shortlist for e in k.rationale.evidence]
bilgi(f"kısa listedeki tüm gerekçe izleri: {len(izler)}")
for k in a.shortlist[:2]:
    for e in k.rationale.evidence:
        bilgi(f"{k.startup.name}: \"{e.brief_phrase}\" ↔ \"{e.startup_capability}\"", girinti=8)
if not gercek_mod():
    kontrol(UYDURMA not in izler, f"'{UYDURMA}' (profilde yok) gerekçe izlerinden atıldı")
kontrol(all(e.startup_capability.lower() in {c.lower() for c in k.startup.capabilities}
            for k in a.shortlist for e in k.rationale.evidence), "kalan her iz girişimin profilinde gerçekten var")

bilgi("Not: koruma sadece yetkinliğin profilde VAR olduğuna bakar, ifadeyle ALAKALI olup olmadığına bakmaz.")
bilgi("Örn. 'şikayetleri sınıflandırmak ↔ randevuya gelmeme tahmini' gibi anlamsız bir iz korumadan geçer.")

adim("E", "Kısa liste skorları (bilinen zayıf nokta)")
birinci = a.shortlist[0].score
dusuk = [k for k in a.shortlist[1:] if k.score < 0.5 * birinci]
bilgi(f"1. adayın skoru: {birinci:.3f}")
bilgi(f"bunun yarısından ({0.5 * birinci:.3f}) düşük skorla kısa listeye giren aday: {len(dusuk)}  "
      f"({', '.join(f'{k.startup.name} {k.score:.2f}' for k in dusuk) or '-'})")
bilgi("→ sistem kaliteden bağımsız her zaman 5 aday gösteriyor; minimum skor eşiği eklenmeli (rapor: sorun #1)")
kontrol(True, "zayıf nokta görünür kılındı (henüz düzeltilmedi)")

bitir()
