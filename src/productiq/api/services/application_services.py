"""Application-level service composition for the HTTP adapter (Phase 13.6)."""

from __future__ import annotations

from dataclasses import dataclass

from productiq.serving.config import ServingConfig
from productiq.serving.protocols import (
    ProductServingService,
    RecommendationServingService,
    SearchServingService,
)


@dataclass(frozen=True)
class ApplicationServices:
    """Long-lived serving services attached to one FastAPI application instance."""

    serving_config: ServingConfig
    search_service: SearchServingService | None = None
    recommendation_service: RecommendationServingService | None = None
    product_service: ProductServingService | None = None

    def configured_service_names(self) -> tuple[str, ...]:
        names: list[str] = []
        if self.search_service is not None:
            names.append("search")
        if self.recommendation_service is not None:
            names.append("recommendation")
        if self.product_service is not None:
            names.append("product")
        return tuple(names)


__all__ = ["ApplicationServices"]
