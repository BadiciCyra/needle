"""Postgres tabloları (SQLAlchemy 2 + pgvector).

"Sadece anlatılan" özellikler (ihtiyacı yaşayan birim, kapalı döngü) kodlanmıyor ama alanları
burada hazır duruyor; sunumda söylenenler veri modelinde karşılık buluyor.
"""

from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
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
    # Firma hesabının ilk girişte doldurduğu profil (api.schemas.OrgProfile); brief'in boş alanlarını besler
    profile: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    onboarded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)  # küçük harfe çevrilmiş
    password_hash: Mapped[str] = mapped_column(String(255))  # argon2id
    name: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20), default="firma")  # firma | yonetici | girisim
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"))
    # Girişim hesabı: sahiplendiği profil. Doğrulanana kadar (alan adı eşleşmesi ya da yönetici onayı)
    # davetleri göremez, profili düzenleyemez.
    startup_id: Mapped[str | None] = mapped_column(ForeignKey("startups.id"))
    startup_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    organization: Mapped[Organization | None] = relationship()
    startup: Mapped["Startup | None"] = relationship()


class AuthSession(Base):
    """Oturum: çerezdeki rastgele anahtarın yalnızca SHA-256 özeti saklanır."""

    __tablename__ = "auth_sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class LoginAttempt(Base):
    """Hatalı giriş denemesi: e-posta ve IP başına sayılır, pencere dışındakiler silinir."""

    __tablename__ = "login_attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), index=True)
    ip: Mapped[str | None] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class PasswordResetToken(Base):
    """Şifre sıfırlama: e-postayla giden anahtarın yalnızca SHA-256 özeti saklanır, tek kullanımlıktır."""

    __tablename__ = "password_reset_tokens"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Need(Base):
    __tablename__ = "needs"

    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"))
    raw_text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    brief: Mapped["BriefRecord | None"] = relationship(back_populates="need")
    organization: Mapped[Organization | None] = relationship()


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
    # Embedding yalnızca aktif profilde var: onay bekleyen yeni profil aramaya hiç girmez
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))
    website: Mapped[str | None] = mapped_column(String(300))  # sahiplenmede e-posta alan adıyla karşılaştırılır
    status: Mapped[str] = mapped_column(String(20), default="aktif")  # aktif | onay_bekliyor | reddedildi
    source: Mapped[str] = mapped_column(String(20), default="havuz")  # havuz (seed) | girisim (kendisi açtı)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


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


class OpenCall(Base):
    """Açık çağrı: havuzda uygun girişim bulunamayan ihtiyaç, girişimlerin başvurusuna açılır."""

    __tablename__ = "open_calls"

    id: Mapped[int] = mapped_column(primary_key=True)
    brief_id: Mapped[int] = mapped_column(ForeignKey("briefs.id"), unique=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    summary: Mapped[str] = mapped_column(Text)  # girişimlerin göreceği metin (brief'in kendisi değil)
    hide_organization: Mapped[bool] = mapped_column(Boolean, default=False)
    deadline: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="acik")  # acik | kapali
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Application(Base):
    __tablename__ = "call_applications"
    __table_args__ = (UniqueConstraint("call_id", "startup_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    call_id: Mapped[int] = mapped_column(ForeignKey("open_calls.id"), index=True)
    startup_id: Mapped[str] = mapped_column(ForeignKey("startups.id"), index=True)
    note: Mapped[str] = mapped_column(Text)  # "bu problemi şöyle çözüyoruz"
    status: Mapped[str] = mapped_column(String(20), default="yeni")  # yeni | kabul | ret
    decision_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Introduction(Base):
    """Tanıştırma: firma bir eşleşmeyi kabul edince girişime giden istek. Girişim kabul ederse pilot açılır."""

    __tablename__ = "introductions"

    id: Mapped[int] = mapped_column(primary_key=True)
    brief_id: Mapped[int] = mapped_column(ForeignKey("briefs.id"), index=True)
    startup_id: Mapped[str] = mapped_column(ForeignKey("startups.id"), index=True)
    match_id: Mapped[int | None] = mapped_column(ForeignKey("matches.id"), unique=True)  # eşleştirmeden geldiyse
    application_id: Mapped[int | None] = mapped_column(ForeignKey("call_applications.id"), unique=True)  # çağrıdan
    status: Mapped[str] = mapped_column(String(20), default="bekliyor")  # bekliyor | kabul | ret
    firm_note: Mapped[str | None] = mapped_column(Text)
    startup_note: Mapped[str | None] = mapped_column(Text)
    # Girişimin hesabı yoksa yönetici onun adına cevap verir ("telefonla görüştüm"); kim cevapladı izlenir
    responded_by: Mapped[str | None] = mapped_column(String(20))  # girisim | yonetici
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Pilot(Base):
    __tablename__ = "pilots"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Pilot ya bir eşleşmeden ya da açık çağrı başvurusundan doğar; brief ve girişim her iki durumda da doğrudan tutulur
    match_id: Mapped[int | None] = mapped_column(ForeignKey("matches.id"), unique=True)
    brief_id: Mapped[int | None] = mapped_column(ForeignKey("briefs.id"), index=True)
    startup_id: Mapped[str | None] = mapped_column(ForeignKey("startups.id"), index=True)
    introduction_id: Mapped[int | None] = mapped_column(ForeignKey("introductions.id"), unique=True)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | paused | done | cancelled
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # Kapalı döngü: pilot sonucu ileride eşleştirme ağırlıklarına geri beslenebilir.
    outcome: Mapped[str | None] = mapped_column(Text)
    outcome_score: Mapped[float | None] = mapped_column(Float)  # eski 0-10 puan; yerini result aldı
    result: Mapped[str | None] = mapped_column(String(10))  # İşe yaradı mı: evet | kismen | hayir


class Milestone(Base):
    __tablename__ = "milestones"

    id: Mapped[int] = mapped_column(primary_key=True)
    pilot_id: Mapped[int] = mapped_column(ForeignKey("pilots.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
