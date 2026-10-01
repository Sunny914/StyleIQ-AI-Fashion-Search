"""Opt-in production search serving performance benchmark (Phase 13.8.3)."""

from __future__ import annotations

import os

import pytest

from productiq.serving.performance.search_benchmark import (
    SEARCH_SERVING_PERFORMANCE_BENCHMARK_ENV,
    run_search_serving_performance_suite,
    write_search_serving_benchmark_artifacts,
)
from productiq.serving.performance.search_benchmark_config import SearchServingBenchmarkSettings
from tests.database.test_integration import INTEGRATION_ENV_VAR, INTEGRATION_SKIP_REASON
from tests.retrieval.integration.conftest import (
    LiveProductionRetrievalContext,
    PRODUCTION_RETRIEVAL_SMOKE_ENV_VAR,
    PRODUCTION_RETRIEVAL_SMOKE_SKIP_REASON,
    production_retrieval_pytestmark,
)

pytest_plugins = ["tests.retrieval.integration.conftest"]

SEARCH_SERVING_PERF_SKIP_REASON = (
    f"Set {SEARCH_SERVING_PERFORMANCE_BENCHMARK_ENV}=1 with PostgreSQL production retrieval enabled "
    f"({INTEGRATION_ENV_VAR}=1 and {PRODUCTION_RETRIEVAL_SMOKE_ENV_VAR}=1)."
)

pytestmark = [
    *production_retrieval_pytestmark,
    pytest.mark.skipif(
        os.getenv(SEARCH_SERVING_PERFORMANCE_BENCHMARK_ENV) != "1",
        reason=SEARCH_SERVING_PERF_SKIP_REASON,
    ),
]


def test_production_search_serving_performance_benchmark(
    live_production_retrieval: LiveProductionRetrievalContext,
) -> None:
    if os.getenv(INTEGRATION_ENV_VAR) != "1":
        pytest.skip(INTEGRATION_SKIP_REASON)
    if os.getenv(PRODUCTION_RETRIEVAL_SMOKE_ENV_VAR) != "1":
        pytest.skip(PRODUCTION_RETRIEVAL_SMOKE_SKIP_REASON)
    settings = SearchServingBenchmarkSettings(warmups=3, iterations=10, concurrency=1)
    suite = run_search_serving_performance_suite(
        live_production_retrieval.pipeline,
        used_full_bm25_index=live_production_retrieval.used_full_bm25_index,
        candidate_pool_top_k=live_production_retrieval.production_config.candidate_pool_top_k,
        settings=settings,
    )
    for result in (*suite.api_results, *suite.service_results):
        assert result.errors.error_count == 0, result.workload.workload_id
        assert result.latency is not None
    write_search_serving_benchmark_artifacts(suite)
