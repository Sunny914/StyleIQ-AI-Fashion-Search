"""FastAPI application factory (Phase 13.2, composition Phase 13.6)."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from productiq.api.exception_handlers import register_exception_handlers
from productiq.api.lifespan import build_lifespan
from productiq.api.middleware.observability import ObservabilityMiddleware
from productiq.api.middleware.request_id import RequestIdMiddleware
from productiq.api.middleware.resilience import ResilienceMiddleware
from productiq.api.routes.v1_router import v1_router
from productiq.api.services.application_services import ApplicationServices
from productiq.api.services.application_wiring import build_application_services
from productiq.api.services.composed_health import ComposedHealthServingService
from productiq.config.runtime_artifacts import resolve_runtime_artifact_paths
from productiq.config.settings import Settings, get_settings
from productiq.observability.runtime.sink import InMemoryObservabilityCollector
from productiq.serving.config import ServingConfig
from productiq.serving.protocols import (
    HealthServingService,
    ProductServingService,
    RecommendationServingService,
    SearchServingService,
)
from productiq.serving.resilience.wiring import build_application_resilience
from productiq.serving.versioning import SERVING_API_MAJOR_VERSION, SERVING_API_ROUTE_PREFIX


def _apply_application_services(app: FastAPI, services: ApplicationServices) -> None:
    app.state.application_services = services
    app.state.serving_config = services.serving_config
    app.state.health_service = ComposedHealthServingService(
        services.serving_config,
        services,
    )
    app.state.search_service = services.search_service
    app.state.recommendation_service = services.recommendation_service
    app.state.product_service = services.product_service


def _configure_cors(app: FastAPI, settings: Settings) -> None:
    if not settings.cors_allowed_origins:
        return
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_allowed_origins),
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )


def create_app(
    *,
    serving_config: ServingConfig | None = None,
    app_settings: Settings | None = None,
    application_services: ApplicationServices | None = None,
    health_service: HealthServingService | None = None,
    search_service: SearchServingService | None = None,
    recommendation_service: RecommendationServingService | None = None,
    product_service: ProductServingService | None = None,
) -> FastAPI:
    """Build a FastAPI application; prefer ``application_services`` for integrated wiring."""
    settings = app_settings or get_settings()
    services = application_services or build_application_services(
        serving_config=serving_config,
        search_service=search_service,
        recommendation_service=recommendation_service,
        product_service=product_service,
    )

    app = FastAPI(
        title="ProductIQ API",
        description="Fashion product search, discovery, and recommendation HTTP API.",
        version=services.serving_config.api_version,
        lifespan=build_lifespan,
        openapi_url=f"{SERVING_API_ROUTE_PREFIX}/openapi.json",
        docs_url=f"{SERVING_API_ROUTE_PREFIX}/docs",
        redoc_url=f"{SERVING_API_ROUTE_PREFIX}/redoc",
    )

    _apply_application_services(app, services)
    app.state.app_settings = settings
    app.state.runtime_artifact_paths = resolve_runtime_artifact_paths(settings)
    if health_service is not None:
        app.state.health_service = health_service
    app.state.is_running = False
    app.state.observability_sink = InMemoryObservabilityCollector()
    app.state.application_resilience = build_application_resilience(services.serving_config)

    _configure_cors(app, settings)
    app.add_middleware(ResilienceMiddleware)
    app.add_middleware(ObservabilityMiddleware)
    app.add_middleware(RequestIdMiddleware)
    register_exception_handlers(app)
    app.include_router(v1_router, prefix=SERVING_API_ROUTE_PREFIX)

    return app


__all__ = ["SERVING_API_MAJOR_VERSION", "create_app"]
