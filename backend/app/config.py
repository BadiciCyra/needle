"""Uygulama ayarları. Hepsi ortam değişkeninden (.env) okunur."""

from functools import lru_cache
from typing import Literal
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), env_file_encoding="utf-8", extra="ignore")

    # Veritabanı
    database_url: str = "postgresql+psycopg://needle:needle@127.0.0.1:5432/needle"

    # LLM: herhangi bir OpenAI uyumlu uç nokta (varsayılan Gemini; Ollama, OmniRoute da olur)
    llm_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    llm_api_key: str = ""
    llm_model: str = "gemini-2.5-flash"
    llm_temperature: float = 0.1
    llm_max_retries: int = 2  # şemaya uymayan cevapta kaç kez yeniden denenecek

    # Demo modu: off = her zaman LLM, record = LLM + önbelleğe yaz, replay = sadece önbellekten
    demo_mode: Literal["off", "record", "replay"] = "off"
    demo_cache_dir: str = "demo_cache"

    # Embedding ve reranker (yerel, açık kaynak)
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    embedding_dim: int = 384
    rerank_backend: Literal["cross_encoder", "llm", "none"] = "llm"  # cross_encoder Türkçe briefte ilgisiz adayları öne alıyordu
    rerank_model: str = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"

    # Dinamik RAG ayarları
    retrieve_top_k: int = 40           # yeniden sıralayıcıya giden aday sayısı (282 girişimlik havuzda 20 dar kalıyordu)
    min_candidates: int = 8            # 5 aday + 3 elenen için gereken en az sayı
    max_retrieval_rounds: int = 3      # yetersiz sonuçta en fazla kaç tur genişletilecek
    shortlist_size: int = 5
    rejected_size: int = 3

    # Güven eşiği (Fikir 1): kısa liste sabit sayıyla değil kaliteyle kesilir
    shortlist_min_score: float = Field(0.003, ge=0, le=1)       # birincinin skoru bunun altındaysa "uygun girişim yok"
    shortlist_relative_ratio: float = Field(0.3, ge=0, le=1)    # birincinin skorunun en az bu oranını alan kısa listeye girer


    # Hesaplar
    session_days: int = 14  # oturum çerezinin geçerlilik süresi
    cookie_secure: bool = False  # HTTPS arkasında yayına alınınca true olmalı

    # Pilot takibi
    pilot_stale_days: int = 10  # bu kadar gün hareketsiz kalan aktif pilot için uyarı

    # Seed: veritabanına yüklenecek girişim dosyası (backend/seed/ altında)
    startups_file: str = "startups_gercek.json"  # gerçek girişimler; kurgusal 40 girişim için startups.json

    # Brief
    max_followup_questions: int = 3


@lru_cache
def get_settings() -> Settings:
    return Settings()
