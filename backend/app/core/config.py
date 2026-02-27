"""
app/core/config.py — Centralised settings via pydantic-settings.
All values read from environment variables / .env file.
"""

from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ───────────────────────────────────────────────
    APP_NAME: str = "B2A Middleware OS"
    APP_ENV: str = "development"
    APP_PORT: int = 8000
    APP_DEBUG: bool = False
    SECRET_KEY: str
    # Store as plain string; split on access for CORS middleware.
    # Set as: ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8000
    ALLOWED_ORIGINS: str = "http://localhost:3000"

    @property
    def allowed_origins_list(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    # ── Database ──────────────────────────────────────────────────
    DATABASE_URL: str

    # ── JWT ───────────────────────────────────────────────────────
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440

    # ── OpenAI ───────────────────────────────────────────────────
    OPENAI_API_KEY: str = ""
    OPENAI_DEFAULT_MODEL: str = "gpt-4o-mini"
    OPENAI_MAX_TOKENS: int = 2048
    OPENAI_TEMPERATURE: float = 0.3
    MOCK_LLM: bool = True
    DEBUG_SKIP_AUTH: bool = True

    # ── Billing ───────────────────────────────────────────────────
    DEFAULT_AGENT_COST_PER_CALL: float = 0.01
    DEFAULT_LLM_COST_PER_1K_TOKENS: float = 0.002
    DEFAULT_WORKFLOW_BASE_COST: float = 0.05

    # ── Observability ─────────────────────────────────────────────
    METRICS_ENABLED: bool = True
    METRICS_PORT: int = 9090
    LOG_LEVEL: str = "INFO"

    # ── Multi-Tenancy ────────────────────────────────────────────
    DEFAULT_TENANT_ID: str = "default"
    MAX_AGENTS_PER_TENANT: int = 50
    MAX_WORKFLOWS_PER_TENANT: int = 1000

    # ── Security ─────────────────────────────────────────────────
    BCRYPT_ROUNDS: int = 12
    API_RATE_LIMIT: int = 100


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings: Settings = get_settings()
