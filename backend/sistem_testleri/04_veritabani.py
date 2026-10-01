"""SİSTEM 4 — Veritabanı (app/db/models.py, app/db/session.py)

Sadece OKUR; hiçbir tabloyu silmez ya da değiştirmez.

Ne gösterir:
  1. Postgres'e bağlantı ve pgvector eklentisinin açık olduğu
  2. 8 tablo ve satır sayıları
  3. Bir girişim satırının içi (JSONB yetkinlikler, 384 boyutlu vektör)
  4. Embedding'i eksik girişim var mı
  5. pgvector benzerlik sorgusunun SQL'i ve sonucu (aynı sorgu iki yoldan: ham SQL ve kodumuz)

Gerekli:  docker compose up -d db   ve   python -m seed.seed_db (bir kez)
Çalıştırma:  python sistem_testleri/04_veritabani.py
"""

from _ortak import adim, baslik, bilgi, bitir, kontrol

from sqlalchemy import inspect, text
from sqlalchemy.dialects import postgresql

from app.config import get_settings
from app.db.models import Base
from app.db.session import get_engine, get_session_factory
from app.embeddings import get_embedder
from app.retrieval.base import SearchQuery
from app.retrieval.pgvector import PgVectorRetriever, build_statement

baslik("SİSTEM 4 — VERİTABANI (Postgres + pgvector)")

adim(1, "Bağlantı ve pgvector eklentisi")
bilgi(f"adres: {get_settings().database_url}")
try:
    with get_engine().connect() as conn:
        surum = conn.execute(text("select version()")).scalar()
        vektor = conn.execute(text("select extversion from pg_extension where extname = 'vector'")).scalar()
except Exception as hata:
    kontrol(False, f"veritabanına bağlanılamadı → Docker açık mı? 'docker compose up -d db'  ({type(hata).__name__})")
    bitir()
bilgi(surum.split(",")[0])
kontrol(vektor is not None, f"pgvector eklentisi açık (sürüm {vektor})")

adim(2, "Tablolar ve satır sayıları")
mevcut = set(inspect(get_engine()).get_table_names())
with get_engine().connect() as conn:
    for tablo in Base.metadata.tables:
        sayi = conn.execute(text(f"select count(*) from {tablo}")).scalar() if tablo in mevcut else "YOK"
        bilgi(f"{tablo:<14} {sayi} satır")
kontrol(set(Base.metadata.tables) <= mevcut, "kodda tanımlı 8 tablonun hepsi veritabanında var")

adim(3, "Bir girişim satırının içi")
with get_engine().connect() as conn:
    satir = conn.execute(text(
        "select id, name, maturity, location, capabilities, vector_dims(embedding) as boyut, "
        "embedding::text as vektor from startups order by id limit 1"
    )).mappings().first()
if satir is None:
    kontrol(False, "startups tablosu boş → 'python -m seed.seed_db' çalıştır")
    bitir()
bilgi(f"{satir['id']} · {satir['name']} · {satir['maturity']} · {satir['location']}")
bilgi(f"yetkinlikler (JSONB): {satir['capabilities']}")
bilgi(f"embedding: {satir['boyut']} boyut, ilk 5 değer: {satir['vektor'][:70]}…")
kontrol(satir["boyut"] == 384, "embedding 384 boyutlu")
kontrol(isinstance(satir["capabilities"], list), "yetkinlikler Python listesi olarak geldi (JSONB)")

adim(4, "Embedding'i eksik girişim var mı?")
with get_engine().connect() as conn:
    toplam, dolu = conn.execute(text("select count(*), count(embedding) from startups")).one()
bilgi(f"{toplam} girişim, {dolu} tanesinin embedding'i var")
kontrol(toplam == dolu == 40, "40 girişimin hepsinin embedding'i dolu")

adim(5, "pgvector benzerlik sorgusu")
soru = "Bayilerden gelen şikayetleri otomatik sınıflandırmak istiyoruz"
vektor = get_embedder().embed_query(soru)
bilgi(f"sorgu: \"{soru}\"")
sorgu = SearchQuery(label="deneme", vector=vektor, top_k=5)
sql = str(build_statement(sorgu).compile(dialect=postgresql.dialect()))
bilgi("kodun ürettiği SQL (vektör parametre olarak gider):")
for satir_sql in sql.splitlines():
    bilgi(satir_sql, girinti=8)

with get_engine().connect() as conn:
    ham = conn.execute(
        text("select name, 1 - (embedding <=> cast(:v as vector)) as benzerlik from startups "
             "order by embedding <=> cast(:v as vector) limit 5"),
        {"v": str(vektor)},
    ).all()
with get_session_factory()() as oturum:
    kodla = PgVectorRetriever(oturum).search(sorgu)

bilgi("sıra  ham SQL                        kodumuz (PgVectorRetriever)")
for i, (a, b) in enumerate(zip(ham, kodla), 1):
    bilgi(f"{i}.    {a.name:<16} {a.benzerlik:.3f}       {b.startup.name:<16} {b.vector_score:.3f}")
kontrol([r.name for r in ham] == [c.startup.name for c in kodla], "ham SQL ile kodumuz aynı sırayı verdi")
kontrol(kodla[0].startup.name == "Metinsel", "en yakın girişim Metinsel (Türkçe metin sınıflandırma)")

bitir()
