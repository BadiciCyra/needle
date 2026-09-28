"""Needle API giriş noktası."""

from fastapi import FastAPI

from app.config import get_settings

app = FastAPI(
    title="Needle API",
    description="Kurum ihtiyacı → brief → gerekçeli eşleştirme → pilot takibi",
    version="0.1.0",
)


@app.get("/health")
def health() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "llm_base_url": settings.llm_base_url,
        "llm_model": settings.llm_model,
        "demo_mode": settings.demo_mode,
    }
