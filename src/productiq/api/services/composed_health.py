"""Health/readiness tied to application service composition (Phase 13.6)."""

from __future__ import annotations

from productiq.api.services.application_services import ApplicationServices
from productiq.serving.config import ServingConfig
from productiq.serving.health import HealthResponse, ReadinessResponse
from productiq.serving.production_safety.readiness import build_readiness_response


class ComposedHealthServingService:
    """Liveness plus configuration-aware readiness (bounded probes only)."""

    def __init__(
        self,
        serving_config: ServingConfig,
        application_services: ApplicationServices,
    ) -> None:
        self._serving_config = serving_config
        self._services = application_services

    def health(self) -> HealthResponse:
        return HealthResponse(
            service=self._serving_config.service_name,
            api_version=self._serving_config.api_version,
        )

    def ready(self) -> ReadinessResponse:
        return build_readiness_response(self._services)


__all__ = ["ComposedHealthServingService"]
