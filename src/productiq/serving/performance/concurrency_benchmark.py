"""Concurrency and throughput sweep orchestration (Phase 13.8.6)."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from productiq.serving.performance.concurrency_benchmark_config import ConcurrencySweepSettings
from productiq.serving.performance.concurrency_schema import (
    CONCURRENCY_SWEEP_CONTRACT_VERSION,
    BenchmarkBoundary,
    ConcurrencyBenchmarkSuiteResult,
    ConcurrencyBenchmarkSweepResult,
    ConcurrencySweepConfiguration,
)
from productiq.serving.performance.concurrency_workloads import concurrency_workload_for_endpoint
from productiq.serving.performance.executors.api import run_api_benchmark
from productiq.serving.performance.executors.service import run_service_benchmark
from productiq.serving.performance.metadata import (
    build_environment_metadata,
    build_serving_configuration_metadata,
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
from productiq.serving.performance.thread_safety_audit import (
    GENERAL_CONCURRENCY_AUDIT_NOTES,
    audit_notes_for_endpoint,
)
from productiq.serving.protocols import (
    ProductServingService,
    RecommendationServingService,
    SearchServingService,
)

PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_CONCURRENCY_BENCHMARK_ARTIFACT_DIR = PROJECT_ROOT / "resources" / "benchmark" / "concurrency"

SERVING_CONCURRENCY_BENCHMARK_ENV = "PRODUCTIQ_SERVING_CONCURRENCY_BENCHMARK"


def build_sweep_configuration(
    workload: ServingPerformanceWorkload,
    settings: ConcurrencySweepSettings,
    *,
    benchmark_boundary: BenchmarkBoundary,
) -> ConcurrencySweepConfiguration:
    return ConcurrencySweepConfiguration(
        endpoint=workload.endpoint,
        workload_id=workload.workload_id,
        benchmark_boundary=benchmark_boundary,
        warmups=settings.warmups,
        iterations=settings.iterations,
        concurrency_levels=settings.concurrency_levels,
    )


def _benchmark_configuration_for_level(
    sweep: ConcurrencySweepConfiguration,
    concurrency: int,
) -> ServingBenchmarkConfiguration:
    return ServingBenchmarkConfiguration(
        benchmark_type=ServingBenchmarkType.CONCURRENCY,
        endpoint=sweep.endpoint,
        workload_id=sweep.workload_id,
        warmups=sweep.warmups,
        iterations=sweep.iterations,
        concurrency=concurrency,
    )


def run_api_concurrency_sweep(
    app: FastAPI,
    workload: ServingPerformanceWorkload,
    settings: ConcurrencySweepSettings | None = None,
    *,
    serving_configuration: ServingConfigurationMetadata | None = None,
    sweep_run_id: str | None = None,
) -> ConcurrencyBenchmarkSweepResult:
    """Run warmups + measured iterations independently at each concurrency level (API boundary)."""
    resolved_settings = settings or ConcurrencySweepSettings()
    sweep_config = build_sweep_configuration(
        workload,
        resolved_settings,
        benchmark_boundary="api",
    )
    serving_config = serving_configuration or build_serving_configuration_metadata()
    environment = build_environment_metadata()
    base_id = sweep_run_id or str(uuid.uuid4())
    run_results: list[ServingBenchmarkRunResult] = []
    with TestClient(app) as client:
        for concurrency in resolved_settings.concurrency_levels:
            configuration = _benchmark_configuration_for_level(sweep_config, concurrency)
            run_results.append(
                run_api_benchmark(
                    client,
                    configuration,
                    workload=workload,
                    benchmark_run_id=f"{base_id}-api-c{concurrency}",
                    serving_configuration=serving_config,
                    environment=environment,
                ),
            )
    notes = audit_notes_for_endpoint(workload.endpoint.value) + GENERAL_CONCURRENCY_AUDIT_NOTES
    return ConcurrencyBenchmarkSweepResult(
        sweep_configuration=sweep_config,
        sweep_run_id=base_id,
        recorded_at_utc=datetime.now(tz=UTC),
        environment=environment,
        serving_configuration=serving_config,
        run_results=tuple(run_results),
        thread_safety_notes=notes,
    )


def run_service_concurrency_sweep(
    workload: ServingPerformanceWorkload,
    settings: ConcurrencySweepSettings | None = None,
    *,
    search_service: SearchServingService | None = None,
    recommendation_service: RecommendationServingService | None = None,
    product_service: ProductServingService | None = None,
    serving_configuration: ServingConfigurationMetadata | None = None,
    sweep_run_id: str | None = None,
) -> ConcurrencyBenchmarkSweepResult:
    """Service-boundary concurrency sweep using the existing service executor."""
    resolved_settings = settings or ConcurrencySweepSettings()
    sweep_config = build_sweep_configuration(
        workload,
        resolved_settings,
        benchmark_boundary="service",
    )
    serving_config = serving_configuration or build_serving_configuration_metadata()
    environment = build_environment_metadata()
    base_id = sweep_run_id or str(uuid.uuid4())
    run_results: list[ServingBenchmarkRunResult] = []
    for concurrency in resolved_settings.concurrency_levels:
        configuration = _benchmark_configuration_for_level(sweep_config, concurrency)
        run_results.append(
            run_service_benchmark(
                configuration,
                workload=workload,
                search_service=search_service,
                recommendation_service=recommendation_service,
                product_service=product_service,
                benchmark_run_id=f"{base_id}-svc-c{concurrency}",
                serving_configuration=serving_config,
                environment=environment,
            ),
        )
    notes = audit_notes_for_endpoint(workload.endpoint.value) + GENERAL_CONCURRENCY_AUDIT_NOTES
    return ConcurrencyBenchmarkSweepResult(
        sweep_configuration=sweep_config,
        sweep_run_id=base_id,
        recorded_at_utc=datetime.now(tz=UTC),
        environment=environment,
        serving_configuration=serving_config,
        run_results=tuple(run_results),
        thread_safety_notes=notes,
    )


def run_endpoint_concurrency_sweeps(
    endpoint: ServingPerformanceEndpoint,
    *,
    app: FastAPI | None = None,
    search_service: SearchServingService | None = None,
    recommendation_service: RecommendationServingService | None = None,
    product_service: ProductServingService | None = None,
    settings: ConcurrencySweepSettings | None = None,
    serving_configuration: ServingConfigurationMetadata | None = None,
    include_api: bool = True,
    include_service: bool = True,
    suite_run_id: str | None = None,
) -> ConcurrencyBenchmarkSuiteResult:
    """Run API and/or service sweeps for one endpoint using the canonical experiment workload."""
    workload = concurrency_workload_for_endpoint(endpoint)
    base_id = suite_run_id or str(uuid.uuid4())
    sweeps: list[ConcurrencyBenchmarkSweepResult] = []
    if include_api:
        if app is None:
            msg = "app is required for API concurrency sweep"
            raise ValueError(msg)
        sweeps.append(
            run_api_concurrency_sweep(
                app,
                workload,
                settings,
                serving_configuration=serving_configuration,
                sweep_run_id=f"{base_id}-{endpoint.value}-api",
            ),
        )
    if include_service:
        sweeps.append(
            run_service_concurrency_sweep(
                workload,
                settings,
                search_service=search_service,
                recommendation_service=recommendation_service,
                product_service=product_service,
                serving_configuration=serving_configuration,
                sweep_run_id=f"{base_id}-{endpoint.value}-svc",
            ),
        )
    return ConcurrencyBenchmarkSuiteResult(
        suite_run_id=base_id,
        recorded_at_utc=datetime.now(tz=UTC),
        sweeps=tuple(sweeps),
    )


def render_concurrency_sweep_report(sweep: ConcurrencyBenchmarkSweepResult) -> str:
    cfg = sweep.sweep_configuration
    lines = [
        "# Concurrency sweep report",
        "",
        f"- **Sweep run ID:** `{sweep.sweep_run_id}`",
        f"- **Recorded (UTC):** {sweep.recorded_at_utc.isoformat()}",
        f"- **Endpoint:** {cfg.endpoint.value}",
        f"- **Boundary:** {cfg.benchmark_boundary}",
        f"- **Workload:** `{cfg.workload_id}`",
        (
            f"- **Warmups / iterations:** {cfg.warmups} / {cfg.iterations} "
            f"(independent per concurrency level)"
        ),
        f"- **Concurrency levels:** {', '.join(str(level) for level in cfg.concurrency_levels)}",
        f"- **Runner version:** {BENCHMARK_RUNNER_VERSION}",
        "",
        "## Measurements",
        "",
        "| Concurrency | P50 ms | P95 ms | P99 ms | Throughput rps | Errors |",
        "|-------------|--------|--------|--------|----------------|--------|",
    ]
    for result in sorted(sweep.run_results, key=lambda row: row.configuration.concurrency):
        concurrency = result.configuration.concurrency
        if result.latency is None:
            lines.append(
                f"| {concurrency} | — | — | — | "
                f"{result.throughput.requests_per_second if result.throughput else 0:.3f} | "
                f"{result.errors.error_count}/{result.errors.total_attempts} |",
            )
            continue
        latency = result.latency
        throughput = result.throughput.requests_per_second if result.throughput else 0.0
        lines.append(
            f"| {concurrency} | {latency.p50_ms:.2f} | {latency.p95_ms:.2f} | "
            f"{latency.p99_ms:.2f} | {throughput:.3f} | "
            f"{result.errors.error_count}/{result.errors.total_attempts} |",
        )
    lines.extend(["", "## Thread-safety notes", ""])
    for note in sweep.thread_safety_notes:
        lines.append(f"- {note}")
    lines.extend(["", "## Limitations", ""])
    for note in sweep.limitations:
        lines.append(f"- {note}")
    lines.append("")
    return "\n".join(lines)


def build_sweep_summary_dict(sweep: ConcurrencyBenchmarkSweepResult) -> dict[str, Any]:
    return {
        "contract_version": CONCURRENCY_SWEEP_CONTRACT_VERSION,
        "sweep_run_id": sweep.sweep_run_id,
        "recorded_at_utc": sweep.recorded_at_utc.isoformat(),
        "sweep_configuration": sweep.sweep_configuration.model_dump(mode="json"),
        "runner_version": BENCHMARK_RUNNER_VERSION,
        "runs": [
            {
                "concurrency": result.configuration.concurrency,
                "benchmark_run_id": result.provenance.benchmark_run_id,
                "success_count": result.errors.success_count,
                "error_count": result.errors.error_count,
                "latency": result.latency.model_dump(mode="json") if result.latency else None,
                "throughput_rps": (
                    result.throughput.requests_per_second if result.throughput else None
                ),
            }
            for result in sweep.run_results
        ],
    }


def write_concurrency_sweep_artifacts(
    sweep: ConcurrencyBenchmarkSweepResult,
    output_dir: Path | None = None,
) -> Path:
    target = output_dir or DEFAULT_CONCURRENCY_BENCHMARK_ARTIFACT_DIR
    target.mkdir(parents=True, exist_ok=True)
    stamp = sweep.recorded_at_utc.strftime("%Y%m%dT%H%M%SZ")
    cfg = sweep.sweep_configuration
    prefix = f"{stamp}_{sweep.sweep_run_id}_{cfg.endpoint.value}_{cfg.benchmark_boundary}"
    (target / f"{prefix}_sweep.json").write_text(
        sweep.model_dump_json(indent=2),
        encoding="utf-8",
    )
    (target / f"{prefix}_summary.json").write_text(
        json.dumps(build_sweep_summary_dict(sweep), indent=2),
        encoding="utf-8",
    )
    (target / f"{prefix}_report.md").write_text(
        render_concurrency_sweep_report(sweep),
        encoding="utf-8",
    )
    return target


def write_concurrency_suite_artifacts(
    suite: ConcurrencyBenchmarkSuiteResult,
    output_dir: Path | None = None,
) -> Path:
    target = output_dir or DEFAULT_CONCURRENCY_BENCHMARK_ARTIFACT_DIR
    for sweep in suite.sweeps:
        write_concurrency_sweep_artifacts(sweep, target)
    stamp = suite.recorded_at_utc.strftime("%Y%m%dT%H%M%SZ")
    (target / f"{stamp}_{suite.suite_run_id}_suite_summary.json").write_text(
        json.dumps(
            {
                "contract_version": CONCURRENCY_SWEEP_CONTRACT_VERSION,
                "suite_run_id": suite.suite_run_id,
                "recorded_at_utc": suite.recorded_at_utc.isoformat(),
                "sweep_ids": [sweep.sweep_run_id for sweep in suite.sweeps],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return target


__all__ = [
    "DEFAULT_CONCURRENCY_BENCHMARK_ARTIFACT_DIR",
    "SERVING_CONCURRENCY_BENCHMARK_ENV",
    "build_sweep_configuration",
    "build_sweep_summary_dict",
    "render_concurrency_sweep_report",
    "run_api_concurrency_sweep",
    "run_endpoint_concurrency_sweeps",
    "run_service_concurrency_sweep",
    "write_concurrency_suite_artifacts",
    "write_concurrency_sweep_artifacts",
]
