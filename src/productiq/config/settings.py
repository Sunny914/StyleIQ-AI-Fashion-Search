"""Application settings loaded from environment variables and optional .env file."""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from pathlib import Path

from pydantic import Field, computed_field, field_validator, model_validator
from pydantic.fields import PrivateAttr
from pydantic_settings import BaseSettings, SettingsConfigDict

from productiq.config.artifacts import (
    DEFAULT_BM25_ARTIFACT,
    DEFAULT_EMBEDDINGS_ARTIFACT,
    DEFAULT_MODEL_ARTIFACTS_DIR,
    DEFAULT_PROCESSED_CATALOG,
    normalize_artifact_path,
)
from productiq.config.cors import (
    default_cors_origins_for_environment,
    parse_cors_origins,
    validate_cors_configuration,
)
from productiq.config.database_config import resolve_database_url
from productiq.config.environment import AppEnvironment, validate_app_environment

_DEV_DATABASE_URL_DEFAULT = "postgresql://productiq:productiq@localhost:5432/productiq"


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

    database_url_override: str | None = Field(
        default=None,
        alias="DATABASE_URL",
        description="PostgreSQL connection URL (sensitive; prefer env at runtime).",
    )
    database_use_component_fields: bool = Field(
        default=False,
        alias="PRODUCTIQ_DATABASE_USE_COMPONENT_FIELDS",
    )
    database_host: str = Field(default="localhost", alias="PRODUCTIQ_DATABASE_HOST")
    database_port: int = Field(default=5432, ge=1, le=65535, alias="PRODUCTIQ_DATABASE_PORT")
    database_name: str = Field(default="productiq", alias="PRODUCTIQ_DATABASE_NAME")
    database_user: str = Field(default="productiq", alias="PRODUCTIQ_DATABASE_USER")
    database_password: str | None = Field(
        default=None,
        alias="DATABASE_PASSWORD",
        description="Database password (secret; not logged).",
    )

    processed_catalog_path: Path = Field(
        default=DEFAULT_PROCESSED_CATALOG,
        alias="PRODUCTIQ_PROCESSED_CATALOG_PATH",
    )
    bm25_artifact_path: Path = Field(
        default=DEFAULT_BM25_ARTIFACT,
        alias="PRODUCTIQ_BM25_ARTIFACT_PATH",
    )
    embeddings_artifact_path: Path = Field(
        default=DEFAULT_EMBEDDINGS_ARTIFACT,
        alias="PRODUCTIQ_EMBEDDINGS_ARTIFACT_PATH",
    )
    model_artifacts_dir: Path = Field(
        default=DEFAULT_MODEL_ARTIFACTS_DIR,
        alias="PRODUCTIQ_MODEL_ARTIFACTS_DIR",
    )

    cors_allowed_origins_input: str = Field(
        default="",
        alias="PRODUCTIQ_CORS_ALLOWED_ORIGINS",
    )
    cors_allow_credentials: bool = Field(
        default=False,
        alias="PRODUCTIQ_CORS_ALLOW_CREDENTIALS",
    )

    _resolved_database_url: str = PrivateAttr(default="")
    _cors_allowed_origins: list[str] = PrivateAttr(default_factory=list)

    @field_validator("app_env", mode="before")
    @classmethod
    def parse_app_env(cls, value: object) -> AppEnvironment:
        if isinstance(value, AppEnvironment):
            return value
        if not isinstance(value, str):
            msg = "app_env must be a string"
            raise TypeError(msg)
        return validate_app_environment(value)

    @field_validator("cors_allowed_origins_input", mode="before")
    @classmethod
    def normalize_cors_input(cls, value: object) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        msg = "cors_allowed_origins_input must be a string"
        raise ValueError(msg)

    @property
    def cors_allowed_origins(self) -> list[str]:
        return list(self._cors_allowed_origins)
    @classmethod
    def validate_processed_catalog_path(cls, value: object) -> Path:
        return normalize_artifact_path(str(value), field_name="processed_catalog_path")

    @field_validator("bm25_artifact_path", mode="before")
    @classmethod
    def validate_bm25_artifact_path(cls, value: object) -> Path:
        return normalize_artifact_path(str(value), field_name="bm25_artifact_path")

    @field_validator("embeddings_artifact_path", mode="before")
    @classmethod
    def validate_embeddings_artifact_path(cls, value: object) -> Path:
        return normalize_artifact_path(str(value), field_name="embeddings_artifact_path")

    @field_validator("model_artifacts_dir", mode="before")
    @classmethod
    def validate_model_artifacts_dir(cls, value: object) -> Path:
        return normalize_artifact_path(str(value), field_name="model_artifacts_dir")

    @model_validator(mode="after")
    def finalize_settings(self) -> Settings:
        origins = parse_cors_origins(self.cors_allowed_origins_input)
        if not origins:
            origins = default_cors_origins_for_environment(self.app_env.value)
        validated_origins = validate_cors_configuration(
            origins=origins,
            allow_credentials=self.cors_allow_credentials,
        )
        object.__setattr__(self, "_cors_allowed_origins", validated_origins)

        resolved = resolve_database_url(
            database_url=self.database_url_override,
            use_component_fields=self.database_use_component_fields,
            host=self.database_host,
            port=self.database_port,
            name=self.database_name,
            user=self.database_user,
            password=self.database_password,
            development_default_url=_DEV_DATABASE_URL_DEFAULT,
        )
        object.__setattr__(self, "_resolved_database_url", resolved)
        self._reject_windows_artifact_paths()
        return self

    def _reject_windows_artifact_paths(self) -> None:
        for field_name in (
            "processed_catalog_path",
            "bm25_artifact_path",
            "embeddings_artifact_path",
            "model_artifacts_dir",
        ):
            path = getattr(self, field_name)
            from productiq.config.database_config import reject_windows_absolute_path

            reject_windows_absolute_path(str(path), field_name=field_name)

    @property
    def database_url(self) -> str:
        """Effective PostgreSQL URL (may contain credentials)."""
        return self._resolved_database_url

    @computed_field  # type: ignore[prop-decorator]
    @property
    def redacted_database_url(self) -> str:
        """Database URL with credentials redacted for safe logging."""
        from productiq.config.database import redact_database_url

        return redact_database_url(self._resolved_database_url)


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()


__all__ = [
    "AppEnvironment",
    "LogLevel",
    "Settings",
    "get_settings",
    "validate_app_environment",
]
