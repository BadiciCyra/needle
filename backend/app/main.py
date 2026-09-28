"""Needle API giriş noktası."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.config import get_settings
from app.llm.cache import DemoCacheMiss
from app.llm.client import StructuredOutputError

logger = logging.getLogger("needle")


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.db.session import init_db

    try:
        init_db()
    except Exception as error:  # veritabanı yoksa API yine açılır; /health durumu gösterir
        logger.warning("Veritabanı başlatılamadı: %s", error)
    yield


app = FastAPI(
    title="Needle API",
    description="Kurum ihtiyacı → brief → gerekçeli eşleştirme → pilot takibi",
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(router)


@app.exception_handler(DemoCacheMiss)
async def demo_cache_miss(_: Request, error: DemoCacheMiss):
    return JSONResponse(status_code=503, content={"detail": f"Demo modu: istek önbellekte yok. {error}"})


@app.exception_handler(StructuredOutputError)
async def structured_output_error(_: Request, error: StructuredOutputError):
    return JSONResponse(status_code=502, content={"detail": f"LLM geçerli cevap üretemedi. {error}"})


@app.get("/health")
def health() -> dict:
    settings = get_settings()
    return {
        "status": "ok",
        "llm_base_url": settings.llm_base_url,
        "llm_model": settings.llm_model,
        "demo_mode": settings.demo_mode,
        "rerank_backend": settings.rerank_backend,
    }
