"""SİSTEM 6 — Dinamik retrieval yapı taşları (app/retrieval/)

Veritabanı gerektirmez: aynı mantığı bellekte çalışan retriever ile, GERÇEK embedding modeliyle gösterir.

Ne gösterir:
  1. Brief'ten çoklu sorgu üretimi (brief + her yetkinlik)
  2. Her sorgunun kendi ilk 5'i
  3. RRF birleştirmesi: birden çok sorguda çıkan aday öne geçer
  4. Filtreler (lokasyon, olgunluk)
  5. Gevşetme merdiveni adım adım
  6. Tercih dışı adaya not düşülmesi

Çalıştırma:  python sistem_testleri/06_retrieval.py
"""

from _ortak import adim, baslik, bilgi, bitir, kontrol

from app.config import get_settings
from app.embeddings import SentenceTransformerEmbedder
from app.retrieval.base import SearchFilters, SearchQuery
from app.retrieval.memory import InMemoryRetriever
from app.retrieval.strategy import RRF_K, annotate_relaxations, build_queries, fuse, initial_filters, relax
from app.schemas import Brief, Maturity
from app.seed_data import load_startups

baslik("SİSTEM 6 — DİNAMİK RETRIEVAL")
ayar = get_settings()
embedder = SentenceTransformerEmbedder(ayar.embedding_model, ayar.embedding_dim)
girisimler = load_startups()
retriever = InMemoryRetriever(girisimler, embedder)
bilgi(f"{len(girisimler)} girişim belleğe yüklendi ve embed edildi")

brief = Brief(
    title="Pompa arızalarını önceden tahmin etme",
    problem="Pompalar arıza yaptıktan sonra fark ediliyor, plansız duruş oluyor",
    required_capabilities=["titreşim sensörüyle kestirimci bakım", "motor ve pompa arıza tahmini"],
    location_preference="Kocaeli",
    min_maturity=Maturity.early_revenue,
)

adim(1, "Çoklu sorgu üretimi")
sorgular = build_queries(brief, embedder, SearchFilters(), top_k=5)
for s in sorgular:
    bilgi(f"[{s.label}]")
kontrol(len(sorgular) == 1 + len(brief.required_capabilities), "1 brief sorgusu + her yetkinlik için 1 sorgu")

adim(2, "Her sorgunun kendi ilk 5'i (filtresiz)")
listeler = []
for s in sorgular:
    sonuc = retriever.search(s)
    listeler.append(sonuc)
    bilgi(f"{s.label}:")
    bilgi(", ".join(f"{c.startup.name}({c.vector_score:.2f})" for c in sonuc), girinti=8)

adim(3, f"RRF birleştirmesi (puan = Σ 1 / ({RRF_K} + sıra))")
birlesik = fuse(listeler)
for c in birlesik[:6]:
    siralar = [next((i + 1 for i, x in enumerate(l) if x.startup.id == c.startup.id), None) for l in listeler]
    puan = sum(1 / (RRF_K + s) for s in siralar if s)
    bilgi(f"{c.startup.name:<18} sorgulardaki sıraları: {siralar}  → RRF puanı {puan:.4f}")
kontrol(birlesik[0].startup.name == "TitreşimAI", "üç sorguda da üstte çıkan TitreşimAI birinci oldu")

adim(4, "Filtreler")
filtre = initial_filters(brief)
bilgi(f"brief'ten gelen filtreler: {filtre.describe()}")
sonuc = retriever.search(SearchQuery(label="brief", vector=sorgular[0].vector, filters=filtre, top_k=20))
bilgi("filtreli sonuç: " + (", ".join(f"{c.startup.name} ({c.startup.location}, {c.startup.maturity.value})"
                                   for c in sonuc) or "(hiç aday yok)"))
kontrol(all(c.startup.location == "Kocaeli" for c in sonuc), "hepsi Kocaeli'de")
kontrol(all(c.startup.maturity in (Maturity.early_revenue, Maturity.growth) for c in sonuc),
        "hepsi en az 'ilk_gelir' olgunluğunda")
bilgi(f"→ sadece {len(sonuc)} aday; 8'den az olduğu için eşleştirme akışı filtreyi gevşetecek")

adim(5, "Gevşetme merdiveni")
basamak = filtre
while (sonraki := relax(basamak)) is not None:
    basamak, not_ = sonraki
    adet = len(retriever.search(SearchQuery(label="b", vector=sorgular[0].vector, filters=basamak, top_k=40)))
    bilgi(f"{not_:<55} → filtreler: {basamak.describe():<28} aday: {adet}")
kontrol(basamak == SearchFilters(), "merdivenin sonunda hiç filtre kalmadı")
kontrol(relax(basamak) is None, "gevşetecek bir şey kalmayınca relax() None döndü")

adim(6, "Tercih dışı adaya not düşülmesi")
notlu = annotate_relaxations(birlesik[:5], brief)
for c in notlu:
    bilgi(f"{c.startup.name:<18} {c.startup.location:<10} {c.startup.maturity.value:<10} notlar: {c.filter_notes or '-'}")
kaliteGoz = next(c for c in notlu if c.startup.name == "KaliteGöz") if any(
    c.startup.name == "KaliteGöz" for c in notlu) else None
kontrol(all(not c.filter_notes for c in notlu if c.startup.location == "Kocaeli"
            and c.startup.maturity in (Maturity.early_revenue, Maturity.growth)), "tercihe uyanlara not düşülmedi")
kontrol(any(c.filter_notes for c in notlu), "tercih dışında kalan en az bir adaya not düşüldü")

bitir()
