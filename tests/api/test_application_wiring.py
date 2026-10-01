"""Tests for Phase 13.6 application service composition."""

from __future__ import annotations

from productiq.api.services.application_wiring import build_application_services
from productiq.api.services.search_wiring import create_search_serving_service_from_pipeline
from productiq.serving.config import ServingConfig
from tests.retrieval.test_production_ranking_integration import _ranked_pipeline


def test_build_application_services_from_pipeline() -> None:
    pipeline, _rrf, _catalog = _ranked_pipeline(ranking=("P1",), pool_top_k=5)
    services = build_application_services(
        serving_config=ServingConfig(service_name="test"),
        search_pipeline=pipeline,
    )
    assert services.serving_config.service_name == "test"
    assert services.search_service is not None
    assert services.recommendation_service is None
    assert services.configured_service_names() == ("search",)


def test_wiring_delegates_to_search_factory() -> None:
    pipeline, _rrf, _catalog = _ranked_pipeline(ranking=("P1",), pool_top_k=5)
    direct = create_search_serving_service_from_pipeline(pipeline)
    via_app = build_application_services(search_pipeline=pipeline).search_service
    assert type(via_app) is type(direct)
