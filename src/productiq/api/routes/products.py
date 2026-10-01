"""Product catalog read API route (Phase 13.5)."""

from __future__ import annotations

from fastapi import APIRouter

from productiq.api.dependencies import ProductServiceDep, RequestIdDep
from productiq.serving.product_schema import ProductApiResponse

products_router = APIRouter(tags=["products"])


@products_router.get("/products/{product_id}", response_model=ProductApiResponse)
def get_product(
    product_id: str,
    service: ProductServiceDep,
    request_id: RequestIdDep,
) -> ProductApiResponse:
    return service.get_product(product_id, request_id=request_id)


__all__ = ["get_product", "products_router"]
