"""Opt-in production concurrency sweeps (Phase 13.8.6)."""

from __future__ import annotations

import os

import pytest

from productiq.api.app import create_app
from productiq.serving.performance.concurrency_benchmark import (
    DEFAULT_CONCURRENCY_BENCHMARK_ARTIFACT_DIR,
    SERVING_CONCURRENCY_BENCHMARK_ENV,
    run_endpoint_concurrency_sweeps,
    write_concurrency_suite_artifacts,
)
from productiq.serving.performance.concurrency_benchmark_config import ConcurrencySweepSettings
from productiq.serving.performance.product_benchmark import (
    DEFAULT_PRODUCT_CATALOG_PARQUET_PATH,
    create_production_product_serving_service_from_parquet,
)
from productiq.serving.performance.product_workloads import (
    validate_product_serving_performance_existing_products,
)
from productiq.serving.performance.schema import ServingPerformanceEndpoint

PRODUCT_CONCURRENCY_SKIP = (
    f"Set {SERVING_CONCURRENCY_BENCHMARK_ENV}=1 and ensure processed catalog parquet exists."
)

pytestmark = pytest.mark.skipif(
    os.getenv(SERVING_CONCURRENCY_BENCHMARK_ENV) != "1"
    or not DEFAULT_PRODUCT_CATALOG_PARQUET_PATH.is_file(),
    reason=PRODUCT_CONCURRENCY_SKIP,
)


def test_production_product_concurrency_sweep() -> None:
    service, catalog = create_production_product_serving_service_from_parquet(
        DEFAULT_PRODUCT_CATALOG_PARQUET_PATH,
    )
    validate_product_serving_performance_existing_products(catalog)
    settings = ConcurrencySweepSettings(warmups=2, iterations=5, concurrency_levels=(1, 2, 4, 8))
    app = create_app(product_service=service)
    suite = run_endpoint_concurrency_sweeps(
        ServingPerformanceEndpoint.PRODUCT,
        app=app,
        product_service=service,
        settings=settings,
        suite_run_id="production-product-concurrency",
    )
    for sweep in suite.sweeps:
        for result in sweep.run_results:
            assert result.errors.error_count == 0, (
                f"c={result.configuration.concurrency} boundary={sweep.sweep_configuration.benchmark_boundary}"
            )
            assert result.latency is not None
    write_concurrency_suite_artifacts(suite, DEFAULT_CONCURRENCY_BENCHMARK_ARTIFACT_DIR)
