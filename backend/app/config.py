"""
config.py — Application settings loaded from environment variables.

All configuration via pydantic-settings. Never hardcode secrets or connection strings.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://fare_engine:dev_password_change_in_prod@localhost:5432/fare_engine"
    TEST_DATABASE_URL: str = "postgresql+asyncpg://fare_engine:dev_password_change_in_prod@localhost:5432/fare_engine_test"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # LLM (Phase 06 — community ingestion)
    CLAUDE_API_KEY: str = ""

    # ITA Matrix Automation (Phase 04)
    ITA_PROXY_LIST: list[str] = []
    ITA_RATE_LIMIT_SECONDS: float = 3.5
    ITA_JITTER_MAX_SECONDS: float = 2.0
    HEADLESS: bool = True

    # API Auth (Phase 09)
    API_KEY_HEADER: str = "X-API-Key"
    INITIAL_API_KEY: str = "dev_key_change_in_production"

    # Alerts (Phase 08)
    ALERT_WEBHOOK_URLS: str = ""
    ALERT_MIN_SEVERITY: str = "MEDIUM"

    # App
    LOG_LEVEL: str = "INFO"
    ENVIRONMENT: str = "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()
