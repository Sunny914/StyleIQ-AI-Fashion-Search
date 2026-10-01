"""Tests for Phase 13.5 product serving service."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from productiq.exceptions.base import CatalogLoadError
from productiq.serving.catalog_read import InMemoryProductCatalogReadProvider
from productiq.serving.processed_catalog_provider import ProcessedParquetProductCatalogReadProvider
from productiq.serving.product_schema import ProductCatalogReadModel
from productiq.serving.product_service import ProductionProductServingService, ProductNotFoundError


def _sample_record(product_id: str = "123456789001") -> ProductCatalogReadModel:
    return ProductCatalogReadModel(
        product_id=product_id,
        brand="puma",
        brand_normalized="puma",
        description="Striped Slim Fit Shirt",
        image_url="https://example.com/img",
        product_url="https://example.com/a",
        category_gender="Men",
        product_type="shirt",
    )


def test_get_product_returns_mapped_response() -> None:
    catalog = InMemoryProductCatalogReadProvider({"123456789001": _sample_record()})
    service = ProductionProductServingService(catalog)
    response = service.get_product("123456789001", request_id="req-prod-1")
    assert response.product_id == "123456789001"
    assert response.brand == "puma"
    assert response.request_id == "req-prod-1"
    assert response.description == "Striped Slim Fit Shirt"


def test_missing_product_raises_not_found() -> None:
    catalog = InMemoryProductCatalogReadProvider({})
    service = ProductionProductServingService(catalog)
    with pytest.raises(ProductNotFoundError):
        service.get_product("missing-id", request_id="req-missing")


def test_product_id_stripped_before_lookup() -> None:
    catalog = InMemoryProductCatalogReadProvider({"P1": _sample_record("P1")})
    service = ProductionProductServingService(catalog)
    response = service.get_product("  P1  ", request_id="req-strip")
    assert response.product_id == "P1"


def test_empty_product_id_invalid_request() -> None:
    service = ProductionProductServingService(InMemoryProductCatalogReadProvider({}))
    with pytest.raises(ValueError):
        service.get_product("   ", request_id="req-empty")


def test_response_excludes_internal_catalog_fields() -> None:
    catalog = InMemoryProductCatalogReadProvider({"P1": _sample_record("P1")})
    service = ProductionProductServingService(catalog)
    response = service.get_product("P1", request_id="req-safe")
    payload = response.model_dump(mode="json")
    assert "brand_normalized" not in payload
    assert "embedding" not in str(payload).lower()
    assert set(payload.keys()) == {
        "product_id",
        "brand",
        "description",
        "image_url",
        "product_url",
        "category_gender",
        "product_type",
        "request_id",
    }


def test_processed_parquet_provider_loads_once(tmp_path: Path) -> None:
    path = tmp_path / "product_catalog.parquet"
    row = {
        "product_id": "123456789001",
        "brand": "puma",
        "brand_normalized": "puma",
        "description": "desc",
        "image_url": "https://example.com/img",
        "product_url": "https://example.com/a",
        "category_gender": "Men",
        "product_type": "shirt",
    }
    pd.DataFrame([row]).to_parquet(path, index=False)
    with patch("productiq.serving.processed_catalog_provider.pd.read_parquet", wraps=pd.read_parquet) as reader:
        provider = ProcessedParquetProductCatalogReadProvider(path)
        assert provider.get_product("123456789001") is not None
        assert provider.get_product("123456789001") is not None
        assert reader.call_count == 1


def test_processed_parquet_missing_file_raises_catalog_load_error(tmp_path: Path) -> None:
    path = tmp_path / "missing.parquet"
    with pytest.raises(CatalogLoadError):
        ProcessedParquetProductCatalogReadProvider(path)
