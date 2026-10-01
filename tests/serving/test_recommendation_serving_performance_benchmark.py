"""Tests for Phase 13.8.4 recommendation serving performance benchmark (offline)."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from productiq.api.app import create_app
from productiq.serving.performance import ServingBenchmarkType, ServingPerformanceEndpoint
from productiq.serving.performance.executors.api import run_api_benchmark
from productiq.serving.performance.executors.service import run_service_benchmark
from productiq.serving.performance.recommendation_benchmark import (
    build_production_recommendation_artifact_identifiers,
    build_recommendation_suite_summary_dict,
    create_production_recommendation_serving_service,
    render_recommendation_serving_benchmark_report,
    run_recommendation_serving_performance_suite,
    write_recommendation_serving_benchmark_artifacts,
)
from productiq.serving.performance.recommendation_benchmark_config import (
    RecommendationServingBenchmarkSettings,
)
from productiq.serving.performance.recommendation_workloads import (
    RECOMMENDATION_SERVING_BRAND_ACTIVITY_V1,
    RECOMMENDATION_SERVING_PERFORMANCE_SEED_IDS,
    RECOMMENDATION_SERVING_PERFORMANCE_WORKLOADS,
    get_recommendation_serving_performance_workload,
)
from productiq.serving.performance.schema import ServingBenchmarkConfiguration
from productiq.serving.performance.timing import ScriptedTimer
from tests.recommendation.test_recommendation_pipeline import _build_catalog, _build_pipeline


def _offline_pipeline_for_performance_seeds() -> object:
    product_ids = tuple(
        dict.fromkeys(
            [
                *RECOMMENDATION_SERVING_PERFORMANCE_SEED_IDS,
                "460825114005",
                "460811249001",
                "469038340002",
                "441118513011",
            ],
        ),
    )
    catalog, filtering = _build_catalog(*product_ids)
    return _build_pipeline(catalog, filtering)


def test_recommendation_workloads_are_unique_and_valid() -> None:
    ids = [workload.workload_id for workload in RECOMMENDATION_SERVING_PERFORMANCE_WORKLOADS]
    assert len(ids) == len(set(ids))
    assert len(ids) == 5
    for workload in RECOMMENDATION_SERVING_PERFORMANCE_WORKLOADS:
        body = workload.request_body or {}
        assert body.get("recommendation_type") == "similar"
        assert body.get("top_k") == 10
        assert body.get("seed_product_id") in RECOMMENDATION_SERVING_PERFORMANCE_SEED_IDS
    assert get_recommendation_serving_performance_workload(
        RECOMMENDATION_SERVING_BRAND_ACTIVITY_V1.workload_id,
    )


def test_artifact_identifiers_structure() -> None:
    deps = build_production_recommendation_artifact_identifiers(used_full_bm25_index=False)
    assert deps.recommendation_stack.startswith("RecommendationPipeline")
    assert deps.recommendation_type == "similar"
    assert deps.artifact_identifiers["candidate_pool_top_k"] == "50"


def test_suite_with_in_memory_pipeline(tmp_path: Path) -> None:
    pipeline = _offline_pipeline_for_performance_seeds()
    settings = RecommendationServingBenchmarkSettings(warmups=1, iterations=2, concurrency=1)
    suite = run_recommendation_serving_performance_suite(
        pipeline,
        used_full_bm25_index=False,
        settings=settings,
        workloads=(RECOMMENDATION_SERVING_BRAND_ACTIVITY_V1,),
    )
    assert len(suite.api_results) == 1
    assert len(suite.service_results) == 1
    assert suite.api_results[0].errors.success_count == 2
    assert suite.service_results[0].latency is not None
    write_recommendation_serving_benchmark_artifacts(suite, tmp_path)
    assert list(tmp_path.glob("*_report.md"))
    assert isinstance(render_recommendation_serving_benchmark_report(suite), str)


def test_suite_summary_json_round_trip() -> None:
    pipeline = _offline_pipeline_for_performance_seeds()
    suite = run_recommendation_serving_performance_suite(
        pipeline,
        used_full_bm25_index=True,
        settings=RecommendationServingBenchmarkSettings(warmups=0, iterations=1, concurrency=1),
        workloads=(RECOMMENDATION_SERVING_BRAND_ACTIVITY_V1,),
    )
    summary = build_recommendation_suite_summary_dict(suite)
    assert summary["settings"]["iterations"] == 1
    assert json.dumps(summary)


def test_production_recommendation_service_wrapper() -> None:
    pipeline = _offline_pipeline_for_performance_seeds()
    service = create_production_recommendation_serving_service(pipeline)
    assert service is not None


def test_service_executor_integration() -> None:
    pipeline = _offline_pipeline_for_performance_seeds()
    service = create_production_recommendation_serving_service(pipeline)
    config = ServingBenchmarkConfiguration(
        benchmark_type=ServingBenchmarkType.SERVICE,
        endpoint=ServingPerformanceEndpoint.RECOMMENDATION,
        workload_id=RECOMMENDATION_SERVING_BRAND_ACTIVITY_V1.workload_id,
        warmups=0,
        iterations=2,
        concurrency=1,
    )
    timer = ScriptedTimer((0.001,) * 20)
    result = run_service_benchmark(
        config,
        workload=RECOMMENDATION_SERVING_BRAND_ACTIVITY_V1,
        recommendation_service=service,
        timer=timer,
    )
    assert result.errors.success_count == 2


def test_api_executor_integration() -> None:
    pipeline = _offline_pipeline_for_performance_seeds()
    service = create_production_recommendation_serving_service(pipeline)
    app = create_app(recommendation_service=service)
    config = ServingBenchmarkConfiguration(
        benchmark_type=ServingBenchmarkType.API,
        endpoint=ServingPerformanceEndpoint.RECOMMENDATION,
        workload_id=RECOMMENDATION_SERVING_BRAND_ACTIVITY_V1.workload_id,
        warmups=0,
        iterations=2,
        concurrency=1,
    )
    timer = ScriptedTimer((0.001,) * 20)
    with TestClient(app) as client:
        result = run_api_benchmark(
            client,
            config,
            workload=RECOMMENDATION_SERVING_BRAND_ACTIVITY_V1,
            timer=timer,
        )
    assert result.errors.success_count == 2


def test_benchmark_opt_in_env_constant_documented() -> None:
    from productiq.serving.performance.recommendation_benchmark import (
        RECOMMENDATION_SERVING_PERFORMANCE_BENCHMARK_ENV,
    )

    assert RECOMMENDATION_SERVING_PERFORMANCE_BENCHMARK_ENV.startswith("PRODUCTIQ_")
