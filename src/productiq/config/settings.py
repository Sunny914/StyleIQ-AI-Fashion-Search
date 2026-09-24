"""Application settings loaded from environment variables and optional .env file."""

from enum import StrEnum
from functools import lru_cache

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEnvironment(StrEnum):
    """Supported deployment environments."""

    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"


class LogLevel(StrEnum):
    """Supported logging levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class Settings(BaseSettings):
    """Typed application configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    app_name: str = Field(default="ProductIQ", alias="APP_NAME")
    app_env: AppEnvironment = Field(default=AppEnvironment.DEVELOPMENT, alias="APP_ENV")
    log_level: LogLevel = Field(default=LogLevel.INFO, alias="LOG_LEVEL")
    database_url: str = Field(
        default="postgresql://productiq:productiq@localhost:5432/productiq",
        alias="DATABASE_URL",
        description="PostgreSQL connection URL (sensitive; do not log verbatim).",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def redacted_database_url(self) -> str:
        """Database URL with credentials redacted for safe logging."""
        from productiq.config.database import redact_database_url

        return redact_database_url(self.database_url)


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
