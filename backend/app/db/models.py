"""Postgres tabloları (SQLAlchemy 2 + pgvector).

"Sadece anlatılan" özellikler (ihtiyacı yaşayan birim, kapalı döngü) kodlanmıyor ama alanları
burada hazır duruyor; sunumda söylenenler veri modelinde karşılık buluyor.
"""

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.config import get_settings

EMBEDDING_DIM = get_settings().embedding_dim


class Base(DeclarativeBase):
    pass


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    sector: Mapped[str | None] = mapped_column(String(100))
    # İhtiyacı yazan birim (ör. inovasyon) ve yaşayan birim (ör. saha satış) ayrı tutulur.
    author_unit: Mapped[str | None] = mapped_column(String(200))
    owner_unit: Mapped[str | None] = mapped_column(String(200))


class Need(Base):
    __tablename__ = "needs"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"))
    raw_text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    brief: Mapped["BriefRecord | None"] = relationship(back_populates="need")


class BriefRecord(Base):
    __tablename__ = "briefs"

    id: Mapped[int] = mapped_column(primary_key=True)
    need_id: Mapped[int] = mapped_column(ForeignKey("needs.id"), unique=True)
    # draft → needs_input (takip sorusu bekliyor) → final
    status: Mapped[str] = mapped_column(String(20), default="draft")
    data: Mapped[dict] = mapped_column(JSONB)                       # schemas.Brief
    followup_questions: Mapped[list] = mapped_column(JSONB, default=list)
    answers: Mapped[dict] = mapped_column(JSONB, default=dict)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    need: Mapped[Need] = relationship(back_populates="brief")


class Startup(Base):
    __tablename__ = "startups"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    sector: Mapped[str] = mapped_column(String(100), index=True)
    maturity: Mapped[str] = mapped_column(String(20), index=True)
    location: Mapped[str] = mapped_column(String(100), index=True)
    capabilities: Mapped[list] = mapped_column(JSONB)
    description: Mapped[str] = mapped_column(Text)
    past_pilots: Mapped[list] = mapped_column(JSONB, default=list)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))


class MatchRun(Base):
    """Bir brief için yapılan eşleştirme turu; dinamik RAG izini saklar."""

    __tablename__ = "match_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    brief_id: Mapped[int] = mapped_column(ForeignKey("briefs.id"), index=True)
    trace: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("match_runs.id"), index=True)
    brief_id: Mapped[int] = mapped_column(ForeignKey("briefs.id"), index=True)
    startup_id: Mapped[str] = mapped_column(ForeignKey("startups.id"))
    kind: Mapped[str] = mapped_column(String(20))            # shortlist | rejected
    rank: Mapped[int] = mapped_column(Integer)
    score: Mapped[float] = mapped_column(Float)
    vector_score: Mapped[float] = mapped_column(Float)
    rerank_score: Mapped[float | None] = mapped_column(Float)
    rationale: Mapped[dict | None] = mapped_column(JSONB)     # gerekçe izleri
    rejection: Mapped[dict | None] = mapped_column(JSONB)     # negatif eşleşme: "yakındı ama X"
    # suggested → accepted (pilot açılır) | declined (program yöneticisi reddetti)
    status: Mapped[str] = mapped_column(String(20), default="suggested")
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Pilot(Base):
    __tablename__ = "pilots"

    id: Mapped[int] = mapped_column(primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), unique=True)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | paused | done | cancelled
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Kapalı döngü: pilot sonucu ileride eşleştirme ağırlıklarına geri beslenebilir.
    outcome: Mapped[str | None] = mapped_column(Text)
    outcome_score: Mapped[float | None] = mapped_column(Float)


class Milestone(Base):
    __tablename__ = "milestones"

    id: Mapped[int] = mapped_column(primary_key=True)
    pilot_id: Mapped[int] = mapped_column(ForeignKey("pilots.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
