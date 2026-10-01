"""Tests for Phase 13.6 readiness semantics."""

from __future__ import annotations

from fastapi.testclient import TestClient

from productiq.api.app import create_app
from productiq.api.services.application_wiring import build_application_services
from productiq.serving.catalog_read import InMemoryProductCatalogReadProvider
from productiq.serving.health import ReadinessStatus
from productiq.serving.product_schema import ProductCatalogReadModel
from productiq.serving.product_service import ProductionProductServingService
from productiq.serving.recommendation_service import ProductionRecommendationServingService
from productiq.serving.search_service import ProductionSearchServingService
from productiq.serving.versioning import PLANNED_ROUTE_READY
from tests.recommendation.test_recommendation_pipeline import _build_catalog, _build_pipeline
from tests.retrieval.test_production_ranking_integration import _ranked_pipeline


def test_ready_not_ready_when_services_unconfigured() -> None:
    app = create_app()
    with TestClient(app) as client:
        body = client.get(PLANNED_ROUTE_READY).json()
    assert body["status"] == ReadinessStatus.NOT_READY.value
    names = {check["name"] for check in body["checks"]}
    assert names == {"search_serving", "recommendation_serving", "product_serving"}


def test_ready_when_all_services_configured() -> None:
    search_pipeline, _rrf, _cat = _ranked_pipeline(ranking=("P1", "P2"), pool_top_k=5)
    rec_catalog, filtering = _build_catalog("P1", "P2")
    rec_pipeline = _build_pipeline(rec_catalog, filtering)
    product_catalog = InMemoryProductCatalogReadProvider(
        {"P1": ProductCatalogReadModel(product_id="P1", brand="nike")},
    )
    services = build_application_services(
        search_service=ProductionSearchServingService(search_pipeline),
        recommendation_service=ProductionRecommendationServingService(rec_pipeline),
        product_service=ProductionProductServingService(product_catalog),
    )
    app = create_app(application_services=services)
    with TestClient(app) as client:
        body = client.get(PLANNED_ROUTE_READY).json()
    assert body["status"] == ReadinessStatus.READY.value
    by_name = {check["name"]: check["status"] for check in body["checks"]}
    assert by_name["search_serving"] == "configured"
    assert by_name["search_retrieval_database"] == "not_checked"
    assert by_name["product_serving"] == "configured"
