"""Health and readiness routes (Phase 13.2)."""

from __future__ import annotations

from fastapi import APIRouter

from productiq.api.dependencies import HealthServiceDep
from productiq.serving.health import HealthResponse, ReadinessResponse

health_router = APIRouter(tags=["health"])


@health_router.get("/health", response_model=HealthResponse)
def get_health(service: HealthServiceDep) -> HealthResponse:
    return service.health()


@health_router.get("/ready", response_model=ReadinessResponse)
def get_ready(service: HealthServiceDep) -> ReadinessResponse:
    return service.ready()


__all__ = ["get_health", "get_ready", "health_router"]
