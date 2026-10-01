"""Production search serving performance benchmark (Phase 13.8.3)."""

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
from productiq.api.services.search_wiring import create_search_serving_service_from_pipeline
from productiq.retrieval.production_pipeline import ProductionRetrievalPipeline
from productiq.serving.performance.executors.api import run_api_benchmark
from productiq.serving.performance.executors.service import run_service_benchmark
from productiq.serving.performance.metadata import build_serving_configuration_metadata
from productiq.serving.performance.runner import BENCHMARK_RUNNER_VERSION
from productiq.serving.performance.schema import (
    ServingBenchmarkConfiguration,
    ServingBenchmarkRunResult,
    ServingBenchmarkType,
    ServingConfigurationMetadata,
    ServingPerformanceEndpoint,
    ServingPerformanceWorkload,
)
from productiq.serving.performance.search_benchmark_config import SearchServingBenchmarkSettings
from productiq.serving.performance.search_workloads import (
    SEARCH_SERVING_PERFORMANCE_WORKLOAD_CATALOG_VERSION,
    SEARCH_SERVING_PERFORMANCE_WORKLOADS,
)
from productiq.serving.protocols import SearchServingService
from productiq.serving.search_service import ProductionSearchServingService

PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_SEARCH_BENCHMARK_ARTIFACT_DIR = PROJECT_ROOT / "resources" / "benchmark" / "search_serving"
BM25_MANIFEST_PATH = PROJECT_ROOT / "resources" / "processed" / "bm25_lexical_index.manifest.json"

SEARCH_SERVING_PERFORMANCE_BENCHMARK_ENV = "PRODUCTIQ_SEARCH_SERVING_PERFORMANCE_BENCHMARK"


@dataclass(frozen=True)
class SearchProductionBenchmarkDependencies:
    """Documented production stack identifiers (no fabricated checksums)."""

    retrieval_stack: str
    bm25_mode: str
    candidate_pool_top_k: int
    rrf_rank_constant: int
    artifact_identifiers: dict[str, str]


@dataclass(frozen=True)
class SearchServingPerformanceSuiteResult:
    benchmark_run_id: str
    recorded_at_utc: datetime
    dependencies: SearchProductionBenchmarkDependencies
    settings: SearchServingBenchmarkSettings
    api_results: tuple[ServingBenchmarkRunResult, ...]
    service_results: tuple[ServingBenchmarkRunResult, ...]


def _load_manifest_field(path: Path, field: str) -> str | None:
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    value = payload.get(field)
    return str(value) if value is not None else None


def build_production_artifact_identifiers(
    *,
    used_full_bm25_index: bool,
    candidate_pool_top_k: int,
) -> SearchProductionBenchmarkDependencies:
    bm25_mode = "full_persisted_index" if used_full_bm25_index else "benchmark_scoped_fallback"
    identifiers: dict[str, str] = {
        "search_workload_catalog_version": SEARCH_SERVING_PERFORMANCE_WORKLOAD_CATALOG_VERSION,
        "retrieval_mechanisms": "bm25,pgvector_semantic,rrf,structured_hard_filter,baseline_ranking",
        "bm25_mode": bm25_mode,
        "candidate_pool_top_k": str(candidate_pool_top_k),
        "rrf_rank_constant": "60",
    }
    checksum = _load_manifest_field(BM25_MANIFEST_PATH, "checksum")
    if checksum is not None:
        identifiers["bm25_index_checksum_sha256"] = checksum
    return SearchProductionBenchmarkDependencies(
        retrieval_stack="ProductionRetrievalPipeline.retrieve_ranked",
        bm25_mode=bm25_mode,
        candidate_pool_top_k=candidate_pool_top_k,
        rrf_rank_constant=60,
        artifact_identifiers=identifiers,
    )


def create_production_search_serving_service(
    pipeline: ProductionRetrievalPipeline,
) -> ProductionSearchServingService:
    service = create_search_serving_service_from_pipeline(pipeline)
    assert isinstance(service, ProductionSearchServingService)
    return service


def _benchmark_configuration(
    benchmark_type: ServingBenchmarkType,
    workload: ServingPerformanceWorkload,
    settings: SearchServingBenchmarkSettings,
) -> ServingBenchmarkConfiguration:
    return ServingBenchmarkConfiguration(
        benchmark_type=benchmark_type,
        endpoint=ServingPerformanceEndpoint.SEARCH,
        workload_id=workload.workload_id,
        iterations=settings.iterations,
        warmups=settings.warmups,
        concurrency=settings.concurrency,
    )


def run_search_api_production_benchmark(
    app: FastAPI,
    workload: ServingPerformanceWorkload,
    settings: SearchServingBenchmarkSettings,
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


def run_search_service_production_benchmark(
    search_service: SearchServingService,
    workload: ServingPerformanceWorkload,
    settings: SearchServingBenchmarkSettings,
    *,
    serving_configuration: ServingConfigurationMetadata,
    benchmark_run_id: str,
) -> ServingBenchmarkRunResult:
    configuration = _benchmark_configuration(ServingBenchmarkType.SERVICE, workload, settings)
    return run_service_benchmark(
        configuration,
        workload=workload,
        search_service=search_service,
        benchmark_run_id=f"{benchmark_run_id}-svc-{workload.workload_id}",
        serving_configuration=serving_configuration,
    )


def run_search_serving_performance_suite(
    pipeline: ProductionRetrievalPipeline,
    *,
    used_full_bm25_index: bool,
    candidate_pool_top_k: int,
    settings: SearchServingBenchmarkSettings | None = None,
    workloads: Sequence[ServingPerformanceWorkload] = SEARCH_SERVING_PERFORMANCE_WORKLOADS,
    benchmark_run_id: str | None = None,
) -> SearchServingPerformanceSuiteResult:
    """Warm production search stack once, then benchmark each workload (API + service)."""
    resolved_settings = settings or SearchServingBenchmarkSettings()
    dependencies = build_production_artifact_identifiers(
        used_full_bm25_index=used_full_bm25_index,
        candidate_pool_top_k=candidate_pool_top_k,
    )
    serving_configuration = build_serving_configuration_metadata(
        artifact_identifiers=dependencies.artifact_identifiers,
    )
    search_service = create_production_search_serving_service(pipeline)
    app = create_app(search_service=search_service)
    run_id = benchmark_run_id or str(uuid.uuid4())

    api_results: list[ServingBenchmarkRunResult] = []
    service_results: list[ServingBenchmarkRunResult] = []
    for workload in workloads:
        api_results.append(
            run_search_api_production_benchmark(
                app,
                workload,
                resolved_settings,
                serving_configuration=serving_configuration,
                benchmark_run_id=run_id,
            ),
        )
        service_results.append(
            run_search_service_production_benchmark(
                search_service,
                workload,
                resolved_settings,
                serving_configuration=serving_configuration,
                benchmark_run_id=run_id,
            ),
        )

    return SearchServingPerformanceSuiteResult(
        benchmark_run_id=run_id,
        recorded_at_utc=datetime.now(tz=UTC),
        dependencies=dependencies,
        settings=resolved_settings,
        api_results=tuple(api_results),
        service_results=tuple(service_results),
    )


def write_search_serving_benchmark_artifacts(
    suite: SearchServingPerformanceSuiteResult,
    output_dir: Path | None = None,
) -> Path:
    target = output_dir or DEFAULT_SEARCH_BENCHMARK_ARTIFACT_DIR
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
        json.dumps(build_suite_summary_dict(suite), indent=2),
        encoding="utf-8",
    )
    report_path = target / f"{stamp}_{suite.benchmark_run_id}_report.md"
    report_path.write_text(render_search_serving_benchmark_report(suite), encoding="utf-8")
    return target


def build_suite_summary_dict(suite: SearchServingPerformanceSuiteResult) -> dict[str, Any]:
    return {
        "benchmark_run_id": suite.benchmark_run_id,
        "recorded_at_utc": suite.recorded_at_utc.isoformat(),
        "runner_version": BENCHMARK_RUNNER_VERSION,
        "settings": suite.settings.model_dump(),
        "dependencies": {
            "retrieval_stack": suite.dependencies.retrieval_stack,
            "bm25_mode": suite.dependencies.bm25_mode,
            "candidate_pool_top_k": suite.dependencies.candidate_pool_top_k,
            "artifact_identifiers": suite.dependencies.artifact_identifiers,
        },
        "workloads": [workload.workload_id for workload in SEARCH_SERVING_PERFORMANCE_WORKLOADS],
    }


def render_search_serving_benchmark_report(suite: SearchServingPerformanceSuiteResult) -> str:
    lines = [
        "# Search serving performance benchmark report",
        "",
        f"- **Run ID:** `{suite.benchmark_run_id}`",
        f"- **Recorded (UTC):** {suite.recorded_at_utc.isoformat()}",
        (
            f"- **Warmups / iterations / concurrency:** {suite.settings.warmups} / "
            f"{suite.settings.iterations} / {suite.settings.concurrency}"
        ),
        f"- **Retrieval stack:** {suite.dependencies.retrieval_stack}",
        f"- **BM25 mode:** {suite.dependencies.bm25_mode}",
        f"- **RRF rank constant:** {suite.dependencies.rrf_rank_constant}",
        "",
        "## Workloads",
        "",
    ]
    for workload in SEARCH_SERVING_PERFORMANCE_WORKLOADS:
        lines.append(f"- `{workload.workload_id}` — {workload.description}")
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
            "Not collected in 13.8.3 (no intrusive pipeline instrumentation).",
            "",
            "## Limitations",
            "",
            "- Absolute latency is environment-specific and not comparable across machines.",
            "- API minus service latency is not reported as HTTP overhead.",
            "- Cold startup is excluded; benchmarks use a warmed application/service.",
            "",
        ],
    )
    return "\n".join(lines)


__all__ = [
    "DEFAULT_SEARCH_BENCHMARK_ARTIFACT_DIR",
    "SEARCH_SERVING_PERFORMANCE_BENCHMARK_ENV",
    "SearchProductionBenchmarkDependencies",
    "SearchServingPerformanceSuiteResult",
    "build_production_artifact_identifiers",
    "create_production_search_serving_service",
    "render_search_serving_benchmark_report",
    "run_search_api_production_benchmark",
    "run_search_service_production_benchmark",
    "run_search_serving_performance_suite",
    "write_search_serving_benchmark_artifacts",
]
