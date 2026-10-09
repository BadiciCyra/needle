"""Veritabanı bağlantısı ve tablo kurulumu."""

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.db.models import Base


@lru_cache
def get_engine() -> Engine:
    return create_engine(get_settings().database_url, pool_pre_ping=True)


def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI bağımlılığı: istek başına bir oturum."""
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


_ADDED_COLUMNS = [
    "ALTER TABLE organizations ADD COLUMN IF NOT EXISTS profile JSONB NOT NULL DEFAULT '{}'",
    "ALTER TABLE organizations ADD COLUMN IF NOT EXISTS onboarded_at TIMESTAMPTZ",
    "ALTER TABLE pilots ADD COLUMN IF NOT EXISTS result VARCHAR(10)",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS startup_id VARCHAR(40) REFERENCES startups(id)",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS startup_verified_at TIMESTAMPTZ",
    "ALTER TABLE startups ADD COLUMN IF NOT EXISTS website VARCHAR(300)",
    "ALTER TABLE startups ADD COLUMN IF NOT EXISTS status VARCHAR(20) NOT NULL DEFAULT 'aktif'",
    "ALTER TABLE startups ADD COLUMN IF NOT EXISTS source VARCHAR(20) NOT NULL DEFAULT 'havuz'",
    "ALTER TABLE startups ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ",
    "ALTER TABLE pilots ALTER COLUMN match_id DROP NOT NULL",
    "ALTER TABLE pilots ADD COLUMN IF NOT EXISTS brief_id INTEGER REFERENCES briefs(id)",
    "ALTER TABLE pilots ADD COLUMN IF NOT EXISTS startup_id VARCHAR(40) REFERENCES startups(id)",
    "ALTER TABLE pilots ADD COLUMN IF NOT EXISTS introduction_id INTEGER REFERENCES introductions(id)",
    "ALTER TABLE startups ADD COLUMN IF NOT EXISTS contact_email VARCHAR(254)",
    "ALTER TABLE startups ADD COLUMN IF NOT EXISTS contact_source VARCHAR(300)",
    "ALTER TABLE introductions ADD COLUMN IF NOT EXISTS email_to VARCHAR(254)",
    "ALTER TABLE introductions ADD COLUMN IF NOT EXISTS email_subject VARCHAR(300)",
    "ALTER TABLE introductions ADD COLUMN IF NOT EXISTS email_body TEXT",
    "ALTER TABLE introductions ADD COLUMN IF NOT EXISTS email_updated_at TIMESTAMPTZ",
    "ALTER TABLE introductions ADD COLUMN IF NOT EXISTS email_sent_at TIMESTAMPTZ",
    "UPDATE pilots p SET brief_id = m.brief_id, startup_id = m.startup_id FROM matches m "
    "WHERE p.match_id = m.id AND p.brief_id IS NULL",
]


def init_db(engine: Engine | None = None) -> None:
    """pgvector eklentisini açar, tabloları oluşturur ve sonradan eklenen sütunları tamamlar."""
    engine = engine or get_engine()
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        for statement in _ADDED_COLUMNS:
            conn.execute(text(statement))
