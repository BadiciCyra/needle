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


# create_all mevcut tablolara sütun eklemez; sonradan eklenen sütunlar burada (MVP için migration yerine)
_ADDED_COLUMNS = [
    "ALTER TABLE organizations ADD COLUMN IF NOT EXISTS profile JSONB NOT NULL DEFAULT '{}'",
    "ALTER TABLE organizations ADD COLUMN IF NOT EXISTS onboarded_at TIMESTAMPTZ",
    "ALTER TABLE pilots ADD COLUMN IF NOT EXISTS result VARCHAR(10)",
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
