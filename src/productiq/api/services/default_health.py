"""Cheap health/readiness implementation for Phase 13.2."""

from __future__ import annotations

from productiq.serving.config import ServingConfig
from productiq.serving.health import HealthResponse, ReadinessResponse, ReadinessStatus


class DefaultHealthServingService:
    """Liveness and readiness without dependency I/O (integration deferred to 13.3+)."""

    def __init__(self, serving_config: ServingConfig) -> None:
        self._serving_config = serving_config

    def health(self) -> HealthResponse:
        return HealthResponse(
            service=self._serving_config.service_name,
            api_version=self._serving_config.api_version,
        )

    def ready(self) -> ReadinessResponse:
        return ReadinessResponse(status=ReadinessStatus.READY, checks=())


__all__ = ["DefaultHealthServingService"]
