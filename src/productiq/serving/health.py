"""Health and readiness response contracts (Phase 13.1)."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class HealthStatus(StrEnum):
    OK = "ok"


class ReadinessStatus(StrEnum):
    READY = "ready"
    NOT_READY = "not_ready"


class DependencyReadinessStatus(StrEnum):
    """Per-dependency probe outcome (Phase 13.10-A)."""

    READY = "ready"
    CONFIGURED = "configured"
    NOT_READY = "not_ready"
    NOT_CHECKED = "not_checked"
    UNKNOWN = "unknown"


class HealthResponse(BaseModel):
    """GET /api/v1/health — process liveness (cheap; no dependency I/O)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: Literal["ok"] = "ok"
    service: str = Field(min_length=1)
    api_version: str = Field(min_length=1)


class ReadinessCheck(BaseModel):
    """One dependency readiness probe (populated in Phase 13.2+)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1)
    status: DependencyReadinessStatus
    message: str | None = None


class ReadinessResponse(BaseModel):
    """GET /api/v1/ready — can the service accept traffic?"""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: ReadinessStatus
    checks: tuple[ReadinessCheck, ...] = ()


__all__ = [
    "DependencyReadinessStatus",
    "HealthResponse",
    "HealthStatus",
    "ReadinessCheck",
    "ReadinessResponse",
    "ReadinessStatus",
]
