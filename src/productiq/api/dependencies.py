"""FastAPI dependency providers (Phase 13.2)."""

from __future__ import annotations

from typing import Annotated, cast

from fastapi import Depends, Request

from productiq.exceptions.base import ConfigurationError
from productiq.serving.config import ServingConfig
from productiq.serving.protocols import (
    HealthServingService,
    ProductServingService,
    RecommendationServingService,
    SearchServingService,
)


def get_serving_config(request: Request) -> ServingConfig:
    return cast(ServingConfig, request.app.state.serving_config)


def get_health_service(request: Request) -> HealthServingService:
    return cast(HealthServingService, request.app.state.health_service)


def get_request_id(request: Request) -> str:
    return cast(str, request.state.request_id)


def get_search_service(request: Request) -> SearchServingService:
    service = getattr(request.app.state, "search_service", None)
    if service is None:
        raise ConfigurationError("Search serving is not configured for this deployment")
    return cast(SearchServingService, service)


def get_recommendation_service(request: Request) -> RecommendationServingService:
    service = getattr(request.app.state, "recommendation_service", None)
    if service is None:
        raise ConfigurationError("Recommendation serving is not configured for this deployment")
    return cast(RecommendationServingService, service)


def get_product_service(request: Request) -> ProductServingService:
    service = getattr(request.app.state, "product_service", None)
    if service is None:
        raise ConfigurationError("Product serving is not configured for this deployment")
    return cast(ProductServingService, service)


ServingConfigDep = Annotated[ServingConfig, Depends(get_serving_config)]
HealthServiceDep = Annotated[HealthServingService, Depends(get_health_service)]
RequestIdDep = Annotated[str, Depends(get_request_id)]
SearchServiceDep = Annotated[SearchServingService, Depends(get_search_service)]
RecommendationServiceDep = Annotated[
    RecommendationServingService,
    Depends(get_recommendation_service),
]
ProductServiceDep = Annotated[ProductServingService, Depends(get_product_service)]


__all__ = [
    "HealthServiceDep",
    "ProductServiceDep",
    "RecommendationServiceDep",
    "RequestIdDep",
    "SearchServiceDep",
    "ServingConfigDep",
    "get_health_service",
    "get_product_service",
    "get_recommendation_service",
    "get_request_id",
    "get_search_service",
    "get_serving_config",
]
