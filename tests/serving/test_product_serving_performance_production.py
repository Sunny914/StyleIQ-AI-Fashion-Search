"""Opt-in production product serving performance benchmark (Phase 13.8.5)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from productiq.serving.performance.product_benchmark import (
    DEFAULT_PRODUCT_CATALOG_PARQUET_PATH,
    PRODUCT_SERVING_PERFORMANCE_BENCHMARK_ENV,
    create_production_product_serving_service_from_parquet,
    run_product_serving_performance_suite,
    write_product_serving_benchmark_artifacts,
)
from productiq.serving.performance.product_benchmark_config import ProductServingBenchmarkSettings
from productiq.serving.performance.product_workloads import (
    validate_product_serving_performance_existing_products,
    validate_product_serving_performance_missing_product_absent,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]

PRODUCT_SERVING_PERF_SKIP_REASON = (
    f"Set {PRODUCT_SERVING_PERFORMANCE_BENCHMARK_ENV}=1 and ensure "
    f"{DEFAULT_PRODUCT_CATALOG_PARQUET_PATH.relative_to(PROJECT_ROOT)} exists."
)

pytestmark = pytest.mark.skipif(
    os.getenv(PRODUCT_SERVING_PERFORMANCE_BENCHMARK_ENV) != "1"
    or not DEFAULT_PRODUCT_CATALOG_PARQUET_PATH.is_file(),
    reason=PRODUCT_SERVING_PERF_SKIP_REASON,
)


def test_production_product_serving_performance_benchmark() -> None:
    _service, catalog = create_production_product_serving_service_from_parquet(
        DEFAULT_PRODUCT_CATALOG_PARQUET_PATH,
    )
    validate_product_serving_performance_existing_products(catalog)
    validate_product_serving_performance_missing_product_absent(catalog)
    settings = ProductServingBenchmarkSettings(warmups=3, iterations=10, concurrency=1)
    suite = run_product_serving_performance_suite(
        catalog,
        catalog_parquet_path=DEFAULT_PRODUCT_CATALOG_PARQUET_PATH,
        settings=settings,
    )
    for result in (*suite.api_results, *suite.service_results):
        assert result.errors.error_count == 0, result.workload.workload_id
        assert result.latency is not None
    write_product_serving_benchmark_artifacts(suite)
