"""Production product read orchestration at the serving boundary (Phase 13.5)."""

from __future__ import annotations

import time

from productiq.exceptions.base import ProductIQError
from productiq.observability.runtime.emitter import observe_stage
from productiq.observability.runtime.serving import emit_product_request_completed, measure_ms
from productiq.observability.tracing import SpanKind
from productiq.serving.catalog_read import ProductCatalogReadProvider
from productiq.serving.errors import ApiErrorCode
from productiq.serving.mappers import product_read_model_to_api
from productiq.serving.product_schema import ProductApiResponse


class ProductNotFoundError(ProductIQError):
    """Raised when the catalog read provider has no row for the requested product_id."""


class ProductionProductServingService:
    """Resolve catalog records and map them to the public product API contract."""

    def __init__(self, catalog: ProductCatalogReadProvider) -> None:
        self._catalog = catalog

    def get_product(self, product_id: str, *, request_id: str) -> ProductApiResponse:
        total_start = time.perf_counter()
        key = product_id.strip()
        if not key:
            msg = "product_id must not be empty"
            raise ValueError(msg)
        try:
            with observe_stage("product.catalog_lookup", kind=SpanKind.SERVING, operation="product.get"):
                record = self._catalog.get_product(key)
            if record is None:
                raise ProductNotFoundError("Product not found.")
            with observe_stage("product.response_mapping", kind=SpanKind.SERVING, operation="product.get"):
                response = product_read_model_to_api(record, request_id=request_id)
        except ProductNotFoundError:
            emit_product_request_completed(
                duration_ms=measure_ms(total_start),
                outcome="failure",
                error_code=ApiErrorCode.NOT_FOUND,
            )
            raise
        emit_product_request_completed(
            duration_ms=measure_ms(total_start),
            outcome="success",
        )
        return response


__all__ = ["ProductNotFoundError", "ProductionProductServingService"]
