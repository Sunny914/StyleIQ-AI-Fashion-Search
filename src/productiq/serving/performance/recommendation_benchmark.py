"""Production recommendation serving performance benchmark (Phase 13.8.4)."""

from __future__ import annotations

import json
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from productiq.api.app import create_app
from productiq.api.services.recommendation_wiring import (
    create_recommendation_serving_service_from_pipeline,
)
from productiq.recommendation.config import DEFAULT_CANDIDATE_POOL_TOP_K
from productiq.recommendation.recommendation_pipeline import RecommendationPipeline
from productiq.serving.performance.executors.api import run_api_benchmark
from productiq.serving.performance.executors.service import run_service_benchmark
from productiq.serving.performance.metadata import build_serving_configuration_metadata
from productiq.serving.performance.recommendation_benchmark_config import (
    RecommendationServingBenchmarkSettings,
)
from productiq.serving.performance.recommendation_workloads import (
    RECOMMENDATION_SERVING_PERFORMANCE_WORKLOAD_CATALOG_VERSION,
    RECOMMENDATION_SERVING_PERFORMANCE_WORKLOADS,
)
from productiq.serving.performance.runner import BENCHMARK_RUNNER_VERSION
from productiq.serving.performance.schema import (
    ServingBenchmarkConfiguration,
    ServingBenchmarkRunResult,
    ServingBenchmarkType,
    ServingConfigurationMetadata,
    ServingPerformanceEndpoint,
    ServingPerformanceWorkload,
)
from productiq.serving.protocols import RecommendationServingService
from productiq.serving.recommendation_service import ProductionRecommendationServingService

PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_RECOMMENDATION_BENCHMARK_ARTIFACT_DIR = (
    PROJECT_ROOT / "resources" / "benchmark" / "recommendation_serving"
)
BM25_MANIFEST_PATH = PROJECT_ROOT / "resources" / "processed" / "bm25_lexical_index.manifest.json"
REPRESENTATIONS_MANIFEST_PATH = (
    PROJECT_ROOT / "resources" / "processed" / "product_representations.manifest.json"
)

RECOMMENDATION_SERVING_PERFORMANCE_BENCHMARK_ENV = (
    "PRODUCTIQ_RECOMMENDATION_SERVING_PERFORMANCE_BENCHMARK"
)


@dataclass(frozen=True)
class RecommendationProductionBenchmarkDependencies:
    """Documented production stack identifiers (no fabricated checksums)."""

    recommendation_stack: str
    bm25_mode: str
    candidate_pool_top_k: int
    recommendation_type: str
    artifact_identifiers: dict[str, str]


@dataclass(frozen=True)
class RecommendationServingPerformanceSuiteResult:
    benchmark_run_id: str
    recorded_at_utc: datetime
    dependencies: RecommendationProductionBenchmarkDependencies
    settings: RecommendationServingBenchmarkSettings
    api_results: tuple[ServingBenchmarkRunResult, ...]
    service_results: tuple[ServingBenchmarkRunResult, ...]


def _load_manifest_field(path: Path, field: str) -> str | None:
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    value = payload.get(field)
    return str(value) if value is not None else None


def build_production_recommendation_artifact_identifiers(
    *,
    used_full_bm25_index: bool,
    candidate_pool_top_k: int = DEFAULT_CANDIDATE_POOL_TOP_K,
) -> RecommendationProductionBenchmarkDependencies:
    bm25_mode = "full_persisted_index" if used_full_bm25_index else "benchmark_scoped_fallback"
    identifiers: dict[str, str] = {
        "recommendation_workload_catalog_version": (
            RECOMMENDATION_SERVING_PERFORMANCE_WORKLOAD_CATALOG_VERSION
        ),
        "recommendation_type": "similar",
        "pipeline_generators": "vector,attribute,bm25",
        "similarity_engine": "ContentSimilarityEngine",
        "ranker": "BaselineRecommendationRanker",
        "bm25_mode": bm25_mode,
        "candidate_pool_top_k": str(candidate_pool_top_k),
        "default_request_top_k": "10",
    }
    bm25_checksum = _load_manifest_field(BM25_MANIFEST_PATH, "checksum")
    if bm25_checksum is not None:
        identifiers["bm25_index_checksum_sha256"] = bm25_checksum
    catalog_checksum = _load_manifest_field(REPRESENTATIONS_MANIFEST_PATH, "checksum")
    if catalog_checksum is not None:
        identifiers["product_representations_checksum_sha256"] = catalog_checksum
    return RecommendationProductionBenchmarkDependencies(
        recommendation_stack="RecommendationPipeline.recommend",
        bm25_mode=bm25_mode,
        candidate_pool_top_k=candidate_pool_top_k,
        recommendation_type="similar",
        artifact_identifiers=identifiers,
    )


def create_production_recommendation_serving_service(
    pipeline: RecommendationPipeline,
) -> ProductionRecommendationServingService:
    service = create_recommendation_serving_service_from_pipeline(pipeline)
    assert isinstance(service, ProductionRecommendationServingService)
    return service


def _benchmark_configuration(
    benchmark_type: ServingBenchmarkType,
    workload: ServingPerformanceWorkload,
    settings: RecommendationServingBenchmarkSettings,
) -> ServingBenchmarkConfiguration:
    return ServingBenchmarkConfiguration(
        benchmark_type=benchmark_type,
        endpoint=ServingPerformanceEndpoint.RECOMMENDATION,
        workload_id=workload.workload_id,
        iterations=settings.iterations,
        warmups=settings.warmups,
        concurrency=settings.concurrency,
    )


def run_recommendation_api_production_benchmark(
    app: FastAPI,
    workload: ServingPerformanceWorkload,
    settings: RecommendationServingBenchmarkSettings,
    *,
    serving_configuration: ServingConfigurationMetadata,
    benchmark_run_id: str,
) -> ServingBenchmarkRunResult:
    configuration = _benchmark_configuration(ServingBenchmarkType.API, workload, settings)
    with TestClient(app) as client:
        return run_api_benchmark(
            client,
            configuration,
            workload=workload,
            benchmark_run_id=f"{benchmark_run_id}-api-{workload.workload_id}",
            serving_configuration=serving_configuration,
        )


def run_recommendation_service_production_benchmark(
    recommendation_service: RecommendationServingService,
    workload: ServingPerformanceWorkload,
    settings: RecommendationServingBenchmarkSettings,
    *,
    serving_configuration: ServingConfigurationMetadata,
    benchmark_run_id: str,
) -> ServingBenchmarkRunResult:
    configuration = _benchmark_configuration(ServingBenchmarkType.SERVICE, workload, settings)
    return run_service_benchmark(
        configuration,
        workload=workload,
        recommendation_service=recommendation_service,
        benchmark_run_id=f"{benchmark_run_id}-svc-{workload.workload_id}",
        serving_configuration=serving_configuration,
    )


def run_recommendation_serving_performance_suite(
    pipeline: RecommendationPipeline,
    *,
    used_full_bm25_index: bool,
    candidate_pool_top_k: int = DEFAULT_CANDIDATE_POOL_TOP_K,
    settings: RecommendationServingBenchmarkSettings | None = None,
    workloads: Sequence[ServingPerformanceWorkload] = RECOMMENDATION_SERVING_PERFORMANCE_WORKLOADS,
    benchmark_run_id: str | None = None,
) -> RecommendationServingPerformanceSuiteResult:
    """Warm production recommendation stack once, then benchmark each workload (API + service)."""
    resolved_settings = settings or RecommendationServingBenchmarkSettings()
    dependencies = build_production_recommendation_artifact_identifiers(
        used_full_bm25_index=used_full_bm25_index,
        candidate_pool_top_k=candidate_pool_top_k,
    )
    serving_configuration = build_serving_configuration_metadata(
        artifact_identifiers=dependencies.artifact_identifiers,
    )
    recommendation_service = create_production_recommendation_serving_service(pipeline)
    app = create_app(recommendation_service=recommendation_service)
    run_id = benchmark_run_id or str(uuid.uuid4())

    api_results: list[ServingBenchmarkRunResult] = []
    service_results: list[ServingBenchmarkRunResult] = []
    for workload in workloads:
        api_results.append(
            run_recommendation_api_production_benchmark(
                app,
                workload,
                resolved_settings,
                serving_configuration=serving_configuration,
                benchmark_run_id=run_id,
            ),
        )
        service_results.append(
            run_recommendation_service_production_benchmark(
                recommendation_service,
                workload,
                resolved_settings,
                serving_configuration=serving_configuration,
                benchmark_run_id=run_id,
            ),
        )

    return RecommendationServingPerformanceSuiteResult(
        benchmark_run_id=run_id,
        recorded_at_utc=datetime.now(tz=UTC),
        dependencies=dependencies,
        settings=resolved_settings,
        api_results=tuple(api_results),
        service_results=tuple(service_results),
    )


def write_recommendation_serving_benchmark_artifacts(
    suite: RecommendationServingPerformanceSuiteResult,
    output_dir: Path | None = None,
) -> Path:
    target = output_dir or DEFAULT_RECOMMENDATION_BENCHMARK_ARTIFACT_DIR
    target.mkdir(parents=True, exist_ok=True)
    stamp = suite.recorded_at_utc.strftime("%Y%m%dT%H%M%SZ")
    for result in (*suite.api_results, *suite.service_results):
        filename = (
            f"{stamp}_{suite.benchmark_run_id}_{result.configuration.benchmark_type.value}_"
            f"{result.workload.workload_id}.json"
        )
        (target / filename).write_text(result.model_dump_json(indent=2), encoding="utf-8")
    summary_path = target / f"{stamp}_{suite.benchmark_run_id}_summary.json"
    summary_path.write_text(
        json.dumps(build_recommendation_suite_summary_dict(suite), indent=2),
        encoding="utf-8",
    )
    report_path = target / f"{stamp}_{suite.benchmark_run_id}_report.md"
    report_path.write_text(render_recommendation_serving_benchmark_report(suite), encoding="utf-8")
    return target


def build_recommendation_suite_summary_dict(
    suite: RecommendationServingPerformanceSuiteResult,
) -> dict[str, Any]:
    return {
        "benchmark_run_id": suite.benchmark_run_id,
        "recorded_at_utc": suite.recorded_at_utc.isoformat(),
        "runner_version": BENCHMARK_RUNNER_VERSION,
        "settings": suite.settings.model_dump(),
        "dependencies": {
            "recommendation_stack": suite.dependencies.recommendation_stack,
            "bm25_mode": suite.dependencies.bm25_mode,
            "candidate_pool_top_k": suite.dependencies.candidate_pool_top_k,
            "recommendation_type": suite.dependencies.recommendation_type,
            "artifact_identifiers": suite.dependencies.artifact_identifiers,
        },
        "workloads": [
            workload.workload_id for workload in RECOMMENDATION_SERVING_PERFORMANCE_WORKLOADS
        ],
    }


def render_recommendation_serving_benchmark_report(
    suite: RecommendationServingPerformanceSuiteResult,
) -> str:
    lines = [
        "# Recommendation serving performance benchmark report",
        "",
        f"- **Run ID:** `{suite.benchmark_run_id}`",
        f"- **Recorded (UTC):** {suite.recorded_at_utc.isoformat()}",
        (
            f"- **Warmups / iterations / concurrency:** {suite.settings.warmups} / "
            f"{suite.settings.iterations} / {suite.settings.concurrency}"
        ),
        f"- **Recommendation stack:** {suite.dependencies.recommendation_stack}",
        f"- **Recommendation type:** {suite.dependencies.recommendation_type}",
        f"- **BM25 mode:** {suite.dependencies.bm25_mode}",
        f"- **Candidate pool top_k (production default):** {suite.dependencies.candidate_pool_top_k}",
        "",
        "## Workloads",
        "",
    ]
    for workload in RECOMMENDATION_SERVING_PERFORMANCE_WORKLOADS:
        body = workload.request_body or {}
        seed = body.get("seed_product_id", "")
        lines.append(
            f"- `{workload.workload_id}` — seed `{seed}` — {workload.description}",
        )
    lines.extend(["", "## Measurements", ""])
    for label, results in (("API", suite.api_results), ("Service", suite.service_results)):
        lines.append(f"### {label} boundary")
        lines.append("")
        for result in results:
            lines.append(f"#### `{result.workload.workload_id}`")
            if result.latency is None:
                lines.append("- Latency: unavailable (all measured executions failed)")
            else:
                latency = result.latency
                lines.append(
                    f"- Latency ms: min={latency.min_ms:.2f} mean={latency.mean_ms:.2f} "
                    f"p50={latency.p50_ms:.2f} p95={latency.p95_ms:.2f} "
                    f"p99={latency.p99_ms:.2f} max={latency.max_ms:.2f}",
                )
            if result.throughput is not None:
                lines.append(
                    f"- Throughput: {result.throughput.requests_per_second:.3f} req/s",
                )
            errors = result.errors
            lines.append(
                f"- Attempts: {errors.total_attempts} success={errors.success_count} "
                f"errors={errors.error_count} rate={errors.error_rate:.3f}",
            )
            lines.append("")
    lines.extend(
        [
            "## Stage measurements",
            "",
            "Not collected in 13.8.4 (no intrusive pipeline instrumentation).",
            "",
            "## Limitations",
            "",
            "- Absolute latency is environment-specific and not comparable across machines.",
            "- API minus service latency is not reported as HTTP overhead.",
            "- Cold startup is excluded; benchmarks use a warmed application/service.",
            "- Attribute generation scans the production catalog each request (measured as-is).",
            "",
        ],
    )
    return "\n".join(lines)


__all__ = [
    "DEFAULT_RECOMMENDATION_BENCHMARK_ARTIFACT_DIR",
    "RECOMMENDATION_SERVING_PERFORMANCE_BENCHMARK_ENV",
    "RecommendationProductionBenchmarkDependencies",
    "RecommendationServingPerformanceSuiteResult",
    "build_production_recommendation_artifact_identifiers",
    "build_recommendation_suite_summary_dict",
    "create_production_recommendation_serving_service",
    "render_recommendation_serving_benchmark_report",
    "run_recommendation_api_production_benchmark",
    "run_recommendation_service_production_benchmark",
    "run_recommendation_serving_performance_suite",
    "write_recommendation_serving_benchmark_artifacts",
]
