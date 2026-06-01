"""
config.py — Production-grade settings with Qdrant Cloud + MLflow support.

New fields vs v2:
  • qdrant_url      — Qdrant Cloud cluster URL (replaces local disk path)
  • qdrant_api_key  — Qdrant Cloud API key
  • mlflow_*        — MLflow tracking URI, experiment name, run tagging
  • environment     — "development" | "production" (controls CORS, log level)
  • allowed_origins — comma-separated CORS origins for production
"""

from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Required secrets ──────────────────────────────────────────────────────
    google_api_key: str = Field(..., description="Google GenAI API key.")
    api_secret_key: str = Field(..., description="X-API-KEY header token.")

    # ── Server ────────────────────────────────────────────────────────────────
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000, ge=1, le=65535)
    environment: str = Field(default="production", description="development | production")
    allowed_origins: str = Field(
        default="*",
        description="Comma-separated CORS origins. Use '*' only in development.",
    )

    # ── Qdrant Cloud ──────────────────────────────────────────────────────────
    qdrant_url: Optional[str] = Field(
        default=None,
        description="Qdrant Cloud cluster URL e.g. https://xyz.qdrant.io:6333",
    )
    qdrant_api_key: Optional[str] = Field(
        default=None,
        description="Qdrant Cloud API key.",
    )
    # Fallback local path (used only when qdrant_url is not set)
    qdrant_storage_path: str = Field(default="./local_qdrant_storage")
    qdrant_collection_name: str = Field(default="resumes")

    # ── Embedding ─────────────────────────────────────────────────────────────
    embedding_model: str = Field(default="BAAI/bge-small-en-v1.5")
    embedding_dimension: int = Field(default=384, ge=1)

    # ── Gemini ────────────────────────────────────────────────────────────────
    gemini_model: str = Field(default="gemini-2.5-flash")

    # ── History CSV ───────────────────────────────────────────────────────────
    history_csv_path: str = Field(default="./matching_history_database.csv")

    # ── MLflow Tracking ───────────────────────────────────────────────────────
    mlflow_tracking_uri: str = Field(
        default="./mlruns",
        description="MLflow tracking URI. Use http://mlflow-server:5000 in production.",
    )
    mlflow_experiment_name: str = Field(
        default="ai-resume-matcher",
        description="MLflow experiment name.",
    )
    mlflow_enabled: bool = Field(
        default=True,
        description="Set to false to disable MLflow tracking.",
    )

    @field_validator("google_api_key", "api_secret_key", mode="before")
    @classmethod
    def _must_not_be_placeholder(cls, value: str, info) -> str:
        placeholders = {"your_google_genai_api_key_here", "your_strong_random_secret_here"}
        stripped = str(value).strip()
        if not stripped:
            raise ValueError(f"{info.field_name} must not be empty.")
        if stripped in placeholders:
            raise ValueError(f"{info.field_name} still contains a placeholder value.")
        return stripped

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def use_qdrant_cloud(self) -> bool:
        return bool(self.qdrant_url and self.qdrant_api_key)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
