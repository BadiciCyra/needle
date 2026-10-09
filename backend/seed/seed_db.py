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


def _extras(filename: str) -> dict[str, dict]:
    """Profil şemasında olmayan seed alanları: site (ilk kaynak) ve sitesinden toplanan iletişim adresi."""
    raw = json.loads((SEED_DIR / filename).read_text(encoding="utf-8"))
    return {
        item["id"]: {
            "website": item["kaynak"][0] if item.get("kaynak") else None,
            "contact_email": (item.get("iletisim") or {}).get("email"),
            "contact_source": (item.get("iletisim") or {}).get("kaynak"),
        }
        for item in raw
    }


def seed_startups() -> int:
    init_db()
    filename = get_settings().startups_file
    startups = load_startups(filename)
    extras = _extras(filename)
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
            **extras.get(s.id, {"website": None, "contact_email": None, "contact_source": None}),
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


def backfill_extras() -> int:
    """Site ve iletişim sütunları sonradan eklendi: dolu veritabanında boş kalanları seed dosyasından tamamlar."""
    changed = 0
    with get_session_factory()() as session:
        for startup_id, extra in _extras(get_settings().startups_file).items():
            for column in ("website", "contact_email", "contact_source"):
                if extra[column]:
                    changed += session.execute(
                        update(Startup)
                        .where(Startup.id == startup_id, getattr(Startup, column).is_(None))
                        .values({column: extra[column]})
                    ).rowcount
        session.commit()
    return changed


def startup_count() -> int:
    init_db()
    with get_session_factory()() as session:
        return session.scalar(select(func.count()).select_from(Startup))


if __name__ == "__main__":
    if "--if-empty" in sys.argv and (existing := startup_count()):
        print(f"Girişim tablosu dolu ({existing} kayıt), seed atlandı; {backfill_extras()} boş site/iletişim alanı dolduruldu.")
    else:
        count = seed_startups()
        print(f"{count} girişim yüklendi.")
