"""HTTP API serving contracts and boundaries (Phase 13.1)."""

from __future__ import annotations

from productiq.serving.config import DEFAULT_API_MAX_TOP_K, ServingConfig
from productiq.serving.errors import (
    ApiErrorBody,
    ApiErrorCode,
    ApiErrorEnvelope,
    map_exception_to_api_error,
    safe_client_message,
)
from productiq.serving.health import (
    DependencyReadinessStatus,
    HealthResponse,
    ReadinessCheck,
    ReadinessResponse,
    ReadinessStatus,
)
from productiq.serving.mappers import (
    product_read_model_to_api,
    ranked_search_to_api_response,
    recommendation_response_to_api,
)
from productiq.serving.product_schema import ProductApiResponse, ProductCatalogReadModel
from productiq.serving.protocols import (
    HealthServingService,
    ProductServingService,
    RecommendationServingService,
    SearchServingService,
)
from productiq.serving.recommendation_schema import (
    RecommendationApiRequest,
    RecommendationApiResponse,
    RecommendationResultItem,
)
from productiq.serving.search_schema import SearchApiRequest, SearchApiResponse, SearchResultItem
from productiq.serving.versioning import (
    PLANNED_ROUTE_HEALTH,
    PLANNED_ROUTE_PRODUCT,
    PLANNED_ROUTE_READY,
    PLANNED_ROUTE_RECOMMENDATIONS,
    PLANNED_ROUTE_SEARCH,
    SERVING_API_MAJOR_VERSION,
    SERVING_API_ROUTE_PREFIX,
)

__all__ = [
    "DEFAULT_API_MAX_TOP_K",
    "PLANNED_ROUTE_HEALTH",
    "PLANNED_ROUTE_PRODUCT",
    "PLANNED_ROUTE_READY",
    "PLANNED_ROUTE_RECOMMENDATIONS",
    "PLANNED_ROUTE_SEARCH",
    "SERVING_API_MAJOR_VERSION",
    "SERVING_API_ROUTE_PREFIX",
    "ApiErrorBody",
    "ApiErrorCode",
    "ApiErrorEnvelope",
    "DependencyReadinessStatus",
    "HealthResponse",
    "HealthServingService",
    "ProductApiResponse",
    "ProductCatalogReadModel",
    "ProductServingService",
    "ReadinessCheck",
    "ReadinessResponse",
    "ReadinessStatus",
    "RecommendationApiRequest",
    "RecommendationApiResponse",
    "RecommendationResultItem",
    "RecommendationServingService",
    "SearchApiRequest",
    "SearchApiResponse",
    "SearchResultItem",
    "SearchServingService",
    "ServingConfig",
    "map_exception_to_api_error",
    "product_read_model_to_api",
    "ranked_search_to_api_response",
    "recommendation_response_to_api",
    "safe_client_message",
]
