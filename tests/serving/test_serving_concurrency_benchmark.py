"""Tests for Phase 13.8.6 concurrency sweep orchestration (offline)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from productiq.api.app import create_app
from productiq.serving.catalog_read import InMemoryProductCatalogReadProvider
from productiq.serving.performance.concurrency_benchmark import (
    SERVING_CONCURRENCY_BENCHMARK_ENV,
    build_sweep_configuration,
    build_sweep_summary_dict,
    render_concurrency_sweep_report,
    run_api_concurrency_sweep,
    run_endpoint_concurrency_sweeps,
    run_service_concurrency_sweep,
    write_concurrency_sweep_artifacts,
)
from productiq.serving.performance.concurrency_benchmark_config import (
    DEFAULT_CONCURRENCY_LEVELS,
    ConcurrencySweepSettings,
)
from productiq.serving.performance.concurrency_schema import ConcurrencyBenchmarkSweepResult
from productiq.serving.performance.concurrency_workloads import (
    CONCURRENCY_EXPERIMENT_WORKLOAD_BY_ENDPOINT,
    concurrency_workload_for_endpoint,
)
from productiq.serving.performance.product_workloads import (
    PRODUCT_SERVING_PERFORMANCE_EXISTING_PRODUCT_IDS,
)
from productiq.serving.performance.schema import ServingPerformanceEndpoint
from productiq.serving.product_service import ProductionProductServingService
from tests.api.fakes import RecordingSearchService
from tests.recommendation.test_recommendation_pipeline import _build_catalog, _build_pipeline
from tests.serving.test_product_service import _sample_record


def test_default_concurrency_levels() -> None:
    assert DEFAULT_CONCURRENCY_LEVELS == (1, 2, 4, 8)


def test_invalid_concurrency_levels_rejected() -> None:
    with pytest.raises(ValueError, match="concurrency_levels"):
        ConcurrencySweepSettings(concurrency_levels=())


def test_workloads_cover_three_endpoints() -> None:
    assert set(CONCURRENCY_EXPERIMENT_WORKLOAD_BY_ENDPOINT) == {
        ServingPerformanceEndpoint.SEARCH,
        ServingPerformanceEndpoint.RECOMMENDATION,
        ServingPerformanceEndpoint.PRODUCT,
    }
    assert (
        concurrency_workload_for_endpoint(ServingPerformanceEndpoint.SEARCH).workload_id
        == "search_serving_lexical_v1"
    )


def test_sweep_configuration_reuses_workload_id() -> None:
    workload = concurrency_workload_for_endpoint(ServingPerformanceEndpoint.PRODUCT)
    settings = ConcurrencySweepSettings(warmups=1, iterations=2, concurrency_levels=(1, 2))
    sweep = build_sweep_configuration(workload, settings, benchmark_boundary="api")
    assert sweep.workload_id == workload.workload_id
    assert sweep.concurrency_levels == (1, 2)


def test_api_sweep_with_fake_search_app() -> None:
    app = create_app(search_service=RecordingSearchService())
    settings = ConcurrencySweepSettings(warmups=0, iterations=3, concurrency_levels=(1, 2))
    workload = concurrency_workload_for_endpoint(ServingPerformanceEndpoint.SEARCH)
    sweep = run_api_concurrency_sweep(app, workload, settings, sweep_run_id="offline-search-api")
    assert isinstance(sweep, ConcurrencyBenchmarkSweepResult)
    assert len(sweep.run_results) == 2
    for result in sweep.run_results:
        assert result.errors.success_count == 3
        assert result.configuration.workload_id == workload.workload_id


def test_service_sweep_with_fake_search_service() -> None:
    settings = ConcurrencySweepSettings(warmups=0, iterations=2, concurrency_levels=(1, 4))
    workload = concurrency_workload_for_endpoint(ServingPerformanceEndpoint.SEARCH)
    sweep = run_service_concurrency_sweep(
        workload,
        settings,
        search_service=RecordingSearchService(),
        sweep_run_id="offline-search-svc",
    )
    assert {result.configuration.concurrency for result in sweep.run_results} == {1, 4}


def test_product_endpoint_suite_api_and_service(tmp_path: Path) -> None:
    records = {
        pid: _sample_record(pid) for pid in PRODUCT_SERVING_PERFORMANCE_EXISTING_PRODUCT_IDS
    }
    catalog = InMemoryProductCatalogReadProvider(records)
    service = ProductionProductServingService(catalog)
    app = create_app(product_service=service)
    settings = ConcurrencySweepSettings(warmups=0, iterations=2, concurrency_levels=(1, 2))
    suite = run_endpoint_concurrency_sweeps(
        ServingPerformanceEndpoint.PRODUCT,
        app=app,
        product_service=service,
        settings=settings,
        suite_run_id="offline-product-suite",
    )
    assert len(suite.sweeps) == 2
    write_concurrency_sweep_artifacts(suite.sweeps[0], tmp_path)
    assert list(tmp_path.glob("*_report.md"))
    assert render_concurrency_sweep_report(suite.sweeps[0])


def test_recommendation_offline_service_sweep() -> None:
    product_ids = ("460946942002", "460825114005", "460811249001")
    catalog, filtering = _build_catalog(*product_ids)
    pipeline = _build_pipeline(catalog, filtering)
    settings = ConcurrencySweepSettings(warmups=0, iterations=1, concurrency_levels=(1,))
    workload = concurrency_workload_for_endpoint(ServingPerformanceEndpoint.RECOMMENDATION)
    from productiq.serving.recommendation_service import ProductionRecommendationServingService

    service = ProductionRecommendationServingService(pipeline)
    sweep = run_service_concurrency_sweep(
        workload,
        settings,
        recommendation_service=service,
    )
    assert sweep.run_results[0].errors.success_count == 1


def test_sweep_summary_json_round_trip() -> None:
    app = create_app(search_service=RecordingSearchService())
    sweep = run_api_concurrency_sweep(
        app,
        concurrency_workload_for_endpoint(ServingPerformanceEndpoint.SEARCH),
        ConcurrencySweepSettings(warmups=0, iterations=1, concurrency_levels=(1,)),
    )
    summary = build_sweep_summary_dict(sweep)
    assert json.dumps(summary)


def test_iterations_must_be_positive() -> None:
    with pytest.raises(ValueError):
        ConcurrencySweepSettings(iterations=0)


def test_opt_in_env_constant() -> None:
    assert SERVING_CONCURRENCY_BENCHMARK_ENV == "PRODUCTIQ_SERVING_CONCURRENCY_BENCHMARK"
