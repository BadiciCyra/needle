"""Uygulama ayarları. Hepsi ortam değişkeninden (.env) okunur."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+psycopg://needle:needle@127.0.0.1:5432/needle"

    llm_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    llm_api_key: str = ""
    llm_model: str = "gemini-2.5-flash"
    llm_temperature: float = 0.1
    llm_max_retries: int = 2

    demo_mode: Literal["off", "record", "replay"] = "off"
    demo_cache_dir: str = "demo_cache"

    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    embedding_dim: int = 384
    rerank_backend: Literal["cross_encoder", "llm", "none"] = "llm"
    rerank_model: str = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
    rerank_verify_top_n: int = 8
    rerank_verify_votes: int = 3

    retrieve_top_k: int = 40
    min_candidates: int = 8
    max_retrieval_rounds: int = 3
    shortlist_size: int = 5
    rejected_size: int = 3

    shortlist_min_score: float | None = Field(None, ge=0, le=1)
    shortlist_relative_ratio: float | None = Field(None, ge=0, le=1)
    evidence_min_similarity: float = Field(0.25, ge=0, le=1)

    session_days: int = 14
    admin_email: str = ""
    admin_password: str = ""
    admin_name: str = "Program yöneticisi"
    startup_domain_autoverify: bool = False
    login_max_failures_per_email: int = 5
    login_max_failures_per_ip: int = 30
    login_window_minutes: int = 15
    password_reset_minutes: int = 60

    app_base_url: str = "http://localhost:3000"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    mail_from: str = "Needle <no-reply@needle.local>"
    cookie_secure: bool = False

    pilot_stale_days: int = 10

    startups_file: str = "startups_gercek.json"

    max_followup_questions: int = 3


@lru_cache
def get_settings() -> Settings:
    return Settings()
