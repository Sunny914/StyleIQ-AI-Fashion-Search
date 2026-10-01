"""Serving-layer configuration boundary (Phase 13.1).

Deployment host/port and FastAPI app wiring belong in Phase 13.2+.
This module defines API-serving limits that complement domain configs.
"""

from __future__ import annotations

import re

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from productiq.config.environment import AppEnvironment, validate_app_environment
from productiq.serving.versioning import SERVING_API_MAJOR_VERSION

DEFAULT_API_MAX_TOP_K = 100
DEFAULT_API_MAX_QUERY_LENGTH = 512
DEFAULT_API_MAX_BODY_BYTES = 1_048_576
_MAX_API_MAX_TOP_K = 1000
_API_VERSION_PATTERN = re.compile(r"^v[0-9]+(?:\.[0-9]+)*$")
_SERVICE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")


class ServingConfig(BaseSettings):
    """Configuration scoped to the HTTP serving boundary."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    api_version: str = Field(default=SERVING_API_MAJOR_VERSION, alias="PRODUCTIQ_API_VERSION")
    api_max_top_k: int = Field(
        default=DEFAULT_API_MAX_TOP_K,
        ge=1,
        le=_MAX_API_MAX_TOP_K,
        alias="PRODUCTIQ_API_MAX_TOP_K",
    )
    service_name: str = Field(default="productiq", alias="PRODUCTIQ_SERVICE_NAME")
    deployment_environment: AppEnvironment = Field(
        default=AppEnvironment.DEVELOPMENT,
        alias="APP_ENV",
        description="Deployment environment (same variable as application Settings).",
    )
    api_max_query_length: int = Field(
        default=DEFAULT_API_MAX_QUERY_LENGTH,
        ge=1,
        le=4096,
        alias="PRODUCTIQ_API_MAX_QUERY_LENGTH",
    )
    api_max_body_bytes: int = Field(
        default=DEFAULT_API_MAX_BODY_BYTES,
        ge=1024,
        le=10_485_760,
        alias="PRODUCTIQ_API_MAX_BODY_BYTES",
    )
    rate_limit_enabled: bool = Field(default=False, alias="PRODUCTIQ_RATE_LIMIT_ENABLED")
    rate_limit_requests_per_window: int = Field(
        default=120,
        ge=1,
        le=100_000,
        alias="PRODUCTIQ_RATE_LIMIT_REQUESTS",
    )
    rate_limit_window_seconds: int = Field(
        default=60,
        ge=1,
        le=3600,
        alias="PRODUCTIQ_RATE_LIMIT_WINDOW_SECONDS",
    )
    rate_limit_max_keys: int = Field(
        default=10_000,
        ge=100,
        le=1_000_000,
        alias="PRODUCTIQ_RATE_LIMIT_MAX_KEYS",
    )
    rate_limit_deployment_key: str = Field(
        default="productiq-default",
        alias="PRODUCTIQ_RATE_LIMIT_DEPLOYMENT_KEY",
    )
    rate_limit_trust_forwarded_for: bool = Field(
        default=False,
        alias="PRODUCTIQ_RATE_LIMIT_TRUST_FORWARDED_FOR",
        description=(
            "When true, X-Forwarded-For may identify clients (trusted reverse proxy only). "
            "When false, only the direct connection peer is used."
        ),
    )
    search_concurrency_limit: int = Field(
        default=0,
        ge=0,
        le=10_000,
        alias="PRODUCTIQ_SEARCH_CONCURRENCY_LIMIT",
    )
    recommendation_concurrency_limit: int = Field(
        default=0,
        ge=0,
        le=10_000,
        alias="PRODUCTIQ_RECOMMENDATION_CONCURRENCY_LIMIT",
    )
    serving_request_timeout_seconds: float = Field(
        default=0.0,
        ge=0.0,
        le=600.0,
        alias="PRODUCTIQ_SERVING_REQUEST_TIMEOUT_SECONDS",
    )

    @field_validator("api_version")
    @classmethod
    def validate_api_version(cls, value: str) -> str:
        candidate = value.strip()
        if not candidate or len(candidate) > 16:
            msg = "api_version must be a bounded version label such as v1"
            raise ValueError(msg)
        if not _API_VERSION_PATTERN.fullmatch(candidate):
            msg = "api_version must match pattern v<major>[.<minor>...]"
            raise ValueError(msg)
        return candidate

    @field_validator("service_name")
    @classmethod
    def validate_service_name(cls, value: str) -> str:
        candidate = value.strip()
        if not candidate or len(candidate) > 64:
            msg = "service_name must be non-empty and at most 64 characters"
            raise ValueError(msg)
        if not _SERVICE_NAME_PATTERN.fullmatch(candidate):
            msg = "service_name contains disallowed characters"
            raise ValueError(msg)
        return candidate

    @field_validator("deployment_environment", mode="before")
    @classmethod
    def validate_deployment_environment(cls, value: object) -> AppEnvironment:
        if isinstance(value, AppEnvironment):
            return value
        if not isinstance(value, str):
            msg = "deployment_environment must be a string"
            raise TypeError(msg)
        return validate_app_environment(value)

    def public_fields(self) -> dict[str, str | int | float | bool]:
        """Non-secret configuration safe for diagnostics (Phase 13.10-A)."""
        return {
            "api_version": self.api_version,
            "api_max_top_k": self.api_max_top_k,
            "api_max_query_length": self.api_max_query_length,
            "api_max_body_bytes": self.api_max_body_bytes,
            "service_name": self.service_name,
            "deployment_environment": self.deployment_environment.value,
            "rate_limit_enabled": self.rate_limit_enabled,
            "rate_limit_requests_per_window": self.rate_limit_requests_per_window,
            "rate_limit_window_seconds": self.rate_limit_window_seconds,
            "rate_limit_trust_forwarded_for": self.rate_limit_trust_forwarded_for,
            "search_concurrency_limit": self.search_concurrency_limit,
            "recommendation_concurrency_limit": self.recommendation_concurrency_limit,
            "serving_request_timeout_seconds": self.serving_request_timeout_seconds,
        }


__all__ = [
    "DEFAULT_API_MAX_BODY_BYTES",
    "DEFAULT_API_MAX_QUERY_LENGTH",
    "DEFAULT_API_MAX_TOP_K",
    "ServingConfig",
]
