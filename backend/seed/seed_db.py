"""Veritabanını kurar ve girişim profillerini embedding'leriyle yükler.

Kullanım (backend klasöründen):
    python -m seed.seed_db                                   # STARTUPS_FILE (varsayılan: gerçek girişimler)
    STARTUPS_FILE=startups.json python -m seed.seed_db       # kurgusal 40 girişim
    python -m seed.seed_db --if-empty                        # tablo boşsa yükle (Docker açılışında)

Tekrar çalıştırmak güvenlidir: aynı id'li girişimler güncellenir.
"""

import json
import sys

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert

from app.config import get_settings
from app.db.models import Startup
from app.db.session import get_session_factory, init_db
from app.embeddings import get_embedder
from app.seed_data import SEED_DIR, load_startups


def _websites(filename: str) -> dict[str, str]:
    """Kaynaklı seed'de ilk kaynak girişimin sitesidir (sahiplenmede e-posta alan adıyla karşılaştırılır)."""
    raw = json.loads((SEED_DIR / filename).read_text(encoding="utf-8"))
    return {item["id"]: item["kaynak"][0] for item in raw if item.get("kaynak")}


def seed_startups() -> int:
    init_db()
    filename = get_settings().startups_file
    startups = load_startups(filename)
    websites = _websites(filename)
    vectors = get_embedder().embed_documents([s.to_search_text() for s in startups])

    rows = [
        {
            "id": s.id,
            "name": s.name,
            "sector": s.sector,
            "maturity": s.maturity.value,
            "location": s.location,
            "capabilities": s.capabilities,
            "description": s.description,
            "past_pilots": s.past_pilots,
            "website": websites.get(s.id),
            "embedding": vector,
        }
        for s, vector in zip(startups, vectors)
    ]
    statement = insert(Startup).values(rows)
    statement = statement.on_conflict_do_update(
        index_elements=[Startup.id],
        set_={c: statement.excluded[c] for c in rows[0] if c != "id"},
    )
    with get_session_factory()() as session:
        session.execute(statement)
        session.commit()
    return len(rows)


def backfill_websites() -> int:
    """Site sütunu sonradan eklendi: dolu veritabanında boş kalanları seed dosyasından tamamlar."""
    with get_session_factory()() as session:
        changed = 0
        for startup_id, url in _websites(get_settings().startups_file).items():
            changed += session.execute(
                update(Startup).where(Startup.id == startup_id, Startup.website.is_(None)).values(website=url)
            ).rowcount
        session.commit()
        return changed


def startup_count() -> int:
    init_db()
    with get_session_factory()() as session:
        return session.scalar(select(func.count()).select_from(Startup))


if __name__ == "__main__":
    if "--if-empty" in sys.argv and (existing := startup_count()):
        print(f"Girişim tablosu dolu ({existing} kayıt), seed atlandı; {backfill_websites()} girişimin sitesi dolduruldu.")
    else:
        count = seed_startups()
        print(f"{count} girişim yüklendi.")
