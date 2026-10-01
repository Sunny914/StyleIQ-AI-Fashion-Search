"""Tests for Phase 13.8.3 search serving performance benchmark (offline)."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from productiq.api.app import create_app
from productiq.serving.performance import ServingBenchmarkType, ServingPerformanceEndpoint
from productiq.serving.performance.executors.api import run_api_benchmark
from productiq.serving.performance.schema import ServingBenchmarkConfiguration
from productiq.serving.performance.search_benchmark import (
    build_production_artifact_identifiers,
    build_suite_summary_dict,
    create_production_search_serving_service,
    render_search_serving_benchmark_report,
    run_search_serving_performance_suite,
    write_search_serving_benchmark_artifacts,
)
from productiq.serving.performance.search_benchmark_config import SearchServingBenchmarkSettings
from productiq.serving.performance.search_workloads import (
    SEARCH_SERVING_LEXICAL_V1,
    SEARCH_SERVING_PERFORMANCE_WORKLOADS,
    get_search_serving_performance_workload,
)
from productiq.serving.performance.timing import ScriptedTimer
from tests.api.fakes import RecordingSearchService
from tests.retrieval.test_production_ranking_integration import _ranked_pipeline


def test_search_workloads_are_unique_and_valid() -> None:
    ids = [workload.workload_id for workload in SEARCH_SERVING_PERFORMANCE_WORKLOADS]
    assert len(ids) == len(set(ids))
    assert len(ids) == 5
    assert get_search_serving_performance_workload(SEARCH_SERVING_LEXICAL_V1.workload_id)


def test_artifact_identifiers_structure() -> None:
    deps = build_production_artifact_identifiers(
        used_full_bm25_index=False,
        candidate_pool_top_k=50,
    )
    assert deps.retrieval_stack.startswith("ProductionRetrievalPipeline")
    assert deps.artifact_identifiers["candidate_pool_top_k"] == "50"


def test_suite_with_in_memory_pipeline(tmp_path: Path) -> None:
    pipeline, _rrf, _catalog = _ranked_pipeline(ranking=("P1", "P2"), pool_top_k=10)
    settings = SearchServingBenchmarkSettings(warmups=1, iterations=2, concurrency=1)
    suite = run_search_serving_performance_suite(
        pipeline,
        used_full_bm25_index=False,
        candidate_pool_top_k=10,
        settings=settings,
        workloads=(SEARCH_SERVING_LEXICAL_V1,),
    )
    assert len(suite.api_results) == 1
    assert len(suite.service_results) == 1
    assert suite.api_results[0].errors.success_count == 2
    assert suite.service_results[0].latency is not None
    write_search_serving_benchmark_artifacts(suite, tmp_path)
    assert list(tmp_path.glob("*_report.md"))
    assert isinstance(render_search_serving_benchmark_report(suite), str)


def test_suite_summary_json_round_trip() -> None:
    pipeline, _rrf, _catalog = _ranked_pipeline(ranking=("P1",), pool_top_k=5)
    suite = run_search_serving_performance_suite(
        pipeline,
        used_full_bm25_index=True,
        candidate_pool_top_k=5,
        settings=SearchServingBenchmarkSettings(warmups=0, iterations=1, concurrency=1),
        workloads=(SEARCH_SERVING_LEXICAL_V1,),
    )
    summary = build_suite_summary_dict(suite)
    assert summary["settings"]["iterations"] == 1
    assert json.dumps(summary)


def test_production_search_service_wrapper() -> None:
    pipeline, _rrf, _catalog = _ranked_pipeline(ranking=("P1",), pool_top_k=5)
    service = create_production_search_serving_service(pipeline)
    assert service is not None


def test_api_executor_integration_with_fake_app() -> None:
    app = create_app(search_service=RecordingSearchService())
    config = ServingBenchmarkConfiguration(
        benchmark_type=ServingBenchmarkType.API,
        endpoint=ServingPerformanceEndpoint.SEARCH,
        workload_id=SEARCH_SERVING_LEXICAL_V1.workload_id,
        warmups=0,
        iterations=2,
        concurrency=1,
    )
    timer = ScriptedTimer((0.001,) * 20)
    with TestClient(app) as client:
        result = run_api_benchmark(
            client,
            config,
            workload=SEARCH_SERVING_LEXICAL_V1,
            timer=timer,
        )
    assert result.errors.success_count == 2
