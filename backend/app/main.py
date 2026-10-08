"""Needle API giriş noktası."""

import logging
from contextlib import asynccontextmanager

import openai
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.auth_routes import router as auth_router
from app.api.collab_routes import router as collab_router
from app.api.routes import router
from app.config import get_settings
from app.llm.cache import DemoCacheMiss
from app.llm.client import LLMNotConfigured, StructuredOutputError

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
app.include_router(auth_router)
app.include_router(router)
app.include_router(collab_router)


@app.exception_handler(DemoCacheMiss)
async def demo_cache_miss(_: Request, error: DemoCacheMiss):
    return JSONResponse(status_code=503, content={"detail": f"Demo modu: istek önbellekte yok. {error}"})


@app.exception_handler(LLMNotConfigured)
async def llm_not_configured(_: Request, __: LLMNotConfigured):
    return JSONResponse(
        status_code=503,
        content={
            "detail": "LLM anahtarı tanımlı değil. .env dosyasında LLM_API_KEY'e Gemini anahtarını yazın "
            "(https://aistudio.google.com/apikey) ve API'yi yeniden başlatın."
        },
    )


@app.exception_handler(openai.AuthenticationError)
async def llm_auth_error(_: Request, error: openai.AuthenticationError):
    return JSONResponse(
        status_code=502,
        content={
            "detail": "LLM isteği reddedildi (geçersiz anahtar). .env dosyasındaki LLM_API_KEY'i kontrol edin. "
            f"Sağlayıcı cevabı: {error.message}"
        },
    )


@app.exception_handler(openai.APIConnectionError)
async def llm_connection_error(_: Request, error: openai.APIConnectionError):
    settings = get_settings()
    return JSONResponse(
        status_code=502,
        content={"detail": f"LLM'e ulaşılamadı ({settings.llm_base_url}). İnternet bağlantısını ve LLM_BASE_URL'i kontrol edin. {error}"},
    )


@app.exception_handler(openai.APIStatusError)
async def llm_status_error(_: Request, error: openai.APIStatusError):
    return JSONResponse(status_code=502, content={"detail": f"LLM sağlayıcısı hata döndürdü ({error.status_code}): {error.message}"})


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
