"""Tests for Phase 13.8.5 product serving performance benchmark (offline)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from productiq.api.app import create_app
from productiq.serving.catalog_read import InMemoryProductCatalogReadProvider
from productiq.serving.performance import ServingBenchmarkType, ServingPerformanceEndpoint
from productiq.serving.performance.executors.api import run_api_benchmark
from productiq.serving.performance.executors.service import run_service_benchmark
from productiq.serving.performance.product_benchmark import (
    PRODUCT_SERVING_PERFORMANCE_BENCHMARK_ENV,
    build_product_suite_summary_dict,
    build_production_product_artifact_identifiers,
    create_production_product_serving_service,
    render_product_serving_benchmark_report,
    run_product_serving_performance_suite,
    write_product_serving_benchmark_artifacts,
)
from productiq.serving.performance.product_benchmark_config import ProductServingBenchmarkSettings
from productiq.serving.performance.product_workloads import (
    PRODUCT_SERVING_EXISTING_V1,
    PRODUCT_SERVING_MISSING_PRODUCT_ID_V1,
    PRODUCT_SERVING_MISSING_V1,
    PRODUCT_SERVING_PERFORMANCE_EXISTING_PRODUCT_IDS,
    PRODUCT_SERVING_PERFORMANCE_SUCCESS_WORKLOADS,
    PRODUCT_SERVING_PERFORMANCE_WORKLOADS,
    get_product_serving_performance_workload,
    validate_product_serving_performance_existing_products,
    validate_product_serving_performance_missing_product_absent,
)
from productiq.serving.performance.schema import ServingBenchmarkConfiguration
from productiq.serving.performance.timing import ScriptedTimer
from productiq.serving.product_service import ProductNotFoundError
from tests.serving.test_product_service import _sample_record


def _in_memory_catalog_for_workloads() -> InMemoryProductCatalogReadProvider:
    records = {
        product_id: _sample_record(product_id)
        for product_id in PRODUCT_SERVING_PERFORMANCE_EXISTING_PRODUCT_IDS
    }
    return InMemoryProductCatalogReadProvider(records)


def test_product_workloads_are_unique_and_valid() -> None:
    ids = [workload.workload_id for workload in PRODUCT_SERVING_PERFORMANCE_WORKLOADS]
    assert len(ids) == len(set(ids))
    assert len(PRODUCT_SERVING_PERFORMANCE_SUCCESS_WORKLOADS) == 3
    assert get_product_serving_performance_workload(PRODUCT_SERVING_EXISTING_V1.workload_id)


def test_in_memory_catalog_validates_existing_and_missing_ids() -> None:
    catalog = _in_memory_catalog_for_workloads()
    validate_product_serving_performance_existing_products(catalog)
    validate_product_serving_performance_missing_product_absent(catalog)


def test_artifact_identifiers_structure(tmp_path: Path) -> None:
    catalog_path = tmp_path / "product_catalog.parquet"
    deps = build_production_product_artifact_identifiers(catalog_parquet_path=catalog_path)
    assert deps.product_stack.startswith("ProductionProductServingService")
    assert "product_workload_catalog_version" in deps.artifact_identifiers


def test_suite_with_in_memory_catalog(tmp_path: Path) -> None:
    catalog = _in_memory_catalog_for_workloads()
    settings = ProductServingBenchmarkSettings(warmups=1, iterations=2, concurrency=1)
    suite = run_product_serving_performance_suite(
        catalog,
        catalog_parquet_path=tmp_path / "unused.parquet",
        settings=settings,
        workloads=(PRODUCT_SERVING_EXISTING_V1,),
    )
    assert len(suite.api_results) == 1
    assert len(suite.service_results) == 1
    assert suite.api_results[0].errors.success_count == 2
    assert suite.service_results[0].latency is not None
    write_product_serving_benchmark_artifacts(suite, tmp_path)
    assert list(tmp_path.glob("*_report.md"))
    assert isinstance(render_product_serving_benchmark_report(suite), str)


def test_suite_summary_json_round_trip() -> None:
    catalog = _in_memory_catalog_for_workloads()
    suite = run_product_serving_performance_suite(
        catalog,
        settings=ProductServingBenchmarkSettings(warmups=0, iterations=1, concurrency=1),
        workloads=(PRODUCT_SERVING_EXISTING_V1,),
    )
    summary = build_product_suite_summary_dict(suite)
    assert summary["settings"]["iterations"] == 1
    assert json.dumps(summary)


def test_api_and_service_executor_integration() -> None:
    catalog = _in_memory_catalog_for_workloads()
    service = create_production_product_serving_service(catalog)
    app = create_app(product_service=service)
    config = ServingBenchmarkConfiguration(
        benchmark_type=ServingBenchmarkType.API,
        endpoint=ServingPerformanceEndpoint.PRODUCT,
        workload_id=PRODUCT_SERVING_EXISTING_V1.workload_id,
        warmups=0,
        iterations=2,
        concurrency=1,
    )
    timer = ScriptedTimer((0.001,) * 20)
    with TestClient(app) as client:
        api_result = run_api_benchmark(
            client,
            config,
            workload=PRODUCT_SERVING_EXISTING_V1,
            timer=timer,
        )
    service_result = run_service_benchmark(
        config.model_copy(update={"benchmark_type": ServingBenchmarkType.SERVICE}),
        workload=PRODUCT_SERVING_EXISTING_V1,
        product_service=service,
        timer=timer,
    )
    assert api_result.errors.success_count == 2
    assert service_result.errors.success_count == 2


def test_missing_product_api_returns_404_contract() -> None:
    catalog = _in_memory_catalog_for_workloads()
    app = create_app(product_service=create_production_product_serving_service(catalog))
    path = PRODUCT_SERVING_MISSING_V1.route_path.format(
        product_id=PRODUCT_SERVING_MISSING_PRODUCT_ID_V1,
    )
    with TestClient(app) as client:
        response = client.get(path)
    assert response.status_code == 404
    payload = response.json()
    assert payload.get("error", {}).get("code") == "NOT_FOUND"


def test_missing_product_service_raises_not_found() -> None:
    service = create_production_product_serving_service(_in_memory_catalog_for_workloads())
    with pytest.raises(ProductNotFoundError):
        service.get_product(PRODUCT_SERVING_MISSING_PRODUCT_ID_V1, request_id="req-missing")


def test_missing_workload_recorded_as_benchmark_error_by_runner() -> None:
    catalog = _in_memory_catalog_for_workloads()
    service = create_production_product_serving_service(catalog)
    app = create_app(product_service=service)
    config = ServingBenchmarkConfiguration(
        benchmark_type=ServingBenchmarkType.API,
        endpoint=ServingPerformanceEndpoint.PRODUCT,
        workload_id=PRODUCT_SERVING_MISSING_V1.workload_id,
        warmups=0,
        iterations=1,
        concurrency=1,
    )
    with TestClient(app) as client:
        result = run_api_benchmark(client, config, workload=PRODUCT_SERVING_MISSING_V1)
    assert result.errors.error_count == 1
    assert result.errors.success_count == 0


def test_benchmark_opt_in_env_constant() -> None:
    assert PRODUCT_SERVING_PERFORMANCE_BENCHMARK_ENV == "PRODUCTIQ_PRODUCT_SERVING_PERFORMANCE_BENCHMARK"
