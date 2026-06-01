"""
main.py — Production FastAPI application factory.

Production changes vs v2:
  • CORS origins loaded from settings.cors_origins (comma-separated env var).
  • Version bumped to 2.0.0.
  • Startup/shutdown events log environment info.
"""

from __future__ import annotations

import logging
import sys

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.config import get_settings
from src.api.endpoints import router as api_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

try:
    settings = get_settings()
except Exception as exc:
    logger.critical("STARTUP FAILURE — invalid config:\n%s", exc)
    sys.exit(1)

app = FastAPI(
    title="AI Resume Matcher",
    description="Production True-RAG pipeline — Qdrant Cloud + Gemini + MLflow.",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event() -> None:
    logger.info(
        "AI Resume Matcher v2.0.0 starting — env=%s, qdrant_cloud=%s, mlflow=%s",
        settings.environment,
        settings.use_qdrant_cloud,
        settings.mlflow_enabled,
    )


@app.on_event("shutdown")
async def shutdown_event() -> None:
    logger.info("AI Resume Matcher shutting down.")


@app.exception_handler(Exception)
async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error: %s %s", request.method, request.url)
    return JSONResponse(status_code=500, content={"detail": "Internal server error."})


app.include_router(api_router, prefix="/api/v1", tags=["Resume Matching"])


@app.get("/", include_in_schema=False)
async def root() -> JSONResponse:
    return JSONResponse(content={
        "service": "AI Resume Matcher",
        "version": "2.0.0",
        "environment": settings.environment,
        "docs": "/docs",
        "health": "/api/v1/health",
    })


if __name__ == "__main__":
    uvicorn.run(
        "src.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.environment == "development",
        log_level="info",
        workers=1 if settings.environment == "development" else 2,
    )
