"""Production product serving performance benchmark (Phase 13.8.5)."""

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
from productiq.api.services.product_wiring import create_product_serving_service_from_catalog
from productiq.serving.catalog_read import ProductCatalogReadProvider
from productiq.serving.performance.executors.api import run_api_benchmark
from productiq.serving.performance.executors.service import run_service_benchmark
from productiq.serving.performance.metadata import build_serving_configuration_metadata
from productiq.serving.performance.product_benchmark_config import ProductServingBenchmarkSettings
from productiq.serving.performance.product_workloads import (
    PRODUCT_SERVING_PERFORMANCE_SUCCESS_WORKLOADS,
    PRODUCT_SERVING_PERFORMANCE_WORKLOAD_CATALOG_VERSION,
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
from productiq.serving.processed_catalog_provider import ProcessedParquetProductCatalogReadProvider
from productiq.serving.product_service import ProductionProductServingService
from productiq.serving.protocols import ProductServingService

PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_PRODUCT_CATALOG_PARQUET_PATH = PROJECT_ROOT / "resources" / "processed" / "product_catalog.parquet"
DEFAULT_PRODUCT_BENCHMARK_ARTIFACT_DIR = PROJECT_ROOT / "resources" / "benchmark" / "product_serving"
PRODUCT_CATALOG_MANIFEST_PATH = PROJECT_ROOT / "resources" / "processed" / "product_catalog.manifest.json"

PRODUCT_SERVING_PERFORMANCE_BENCHMARK_ENV = "PRODUCTIQ_PRODUCT_SERVING_PERFORMANCE_BENCHMARK"


@dataclass(frozen=True)
class ProductProductionBenchmarkDependencies:
    """Documented production stack identifiers (no fabricated checksums)."""

    product_stack: str
    catalog_artifact_path: str
    catalog_row_count: int | None
    artifact_identifiers: dict[str, str]


@dataclass(frozen=True)
class ProductServingPerformanceSuiteResult:
    benchmark_run_id: str
    recorded_at_utc: datetime
    dependencies: ProductProductionBenchmarkDependencies
    settings: ProductServingBenchmarkSettings
    api_results: tuple[ServingBenchmarkRunResult, ...]
    service_results: tuple[ServingBenchmarkRunResult, ...]


def _load_manifest_field(path: Path, field: str) -> str | None:
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    value = payload.get(field)
    return str(value) if value is not None else None


def _manifest_row_count(path: Path) -> int | None:
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    row_count = payload.get("row_count")
    return int(row_count) if isinstance(row_count, int) else None


def _catalog_artifact_label(catalog_parquet_path: Path) -> str:
    try:
        return str(catalog_parquet_path.relative_to(PROJECT_ROOT)).replace("\\", "/")
    except ValueError:
        return str(catalog_parquet_path)


def build_production_product_artifact_identifiers(
    *,
    catalog_parquet_path: Path,
) -> ProductProductionBenchmarkDependencies:
    identifiers: dict[str, str] = {
        "product_workload_catalog_version": PRODUCT_SERVING_PERFORMANCE_WORKLOAD_CATALOG_VERSION,
        "catalog_artifact": _catalog_artifact_label(catalog_parquet_path),
        "catalog_provider": "ProcessedParquetProductCatalogReadProvider",
        "lookup": "in_memory_index_o1",
    }
    checksum = _load_manifest_field(PRODUCT_CATALOG_MANIFEST_PATH, "checksum")
    if checksum is not None:
        identifiers["product_catalog_checksum_sha256"] = checksum
    schema_version = _load_manifest_field(PRODUCT_CATALOG_MANIFEST_PATH, "schema_version")
    if schema_version is not None:
        identifiers["product_catalog_schema_version"] = schema_version
    return ProductProductionBenchmarkDependencies(
        product_stack="ProductionProductServingService.get_product",
        catalog_artifact_path=str(catalog_parquet_path),
        catalog_row_count=_manifest_row_count(PRODUCT_CATALOG_MANIFEST_PATH),
        artifact_identifiers=identifiers,
    )


def create_production_product_catalog_provider(
    catalog_parquet_path: Path | None = None,
) -> ProcessedParquetProductCatalogReadProvider:
    path = catalog_parquet_path or DEFAULT_PRODUCT_CATALOG_PARQUET_PATH
    return ProcessedParquetProductCatalogReadProvider(path)


def create_production_product_serving_service(
    catalog: ProductCatalogReadProvider,
) -> ProductionProductServingService:
    service = create_product_serving_service_from_catalog(catalog)
    assert isinstance(service, ProductionProductServingService)
    return service


def create_production_product_serving_service_from_parquet(
    catalog_parquet_path: Path | None = None,
) -> tuple[ProductionProductServingService, ProcessedParquetProductCatalogReadProvider]:
    """Load parquet index once, return service + provider for validation hooks."""
    path = catalog_parquet_path or DEFAULT_PRODUCT_CATALOG_PARQUET_PATH
    catalog = ProcessedParquetProductCatalogReadProvider(path)
    service = create_production_product_serving_service(catalog)
    return service, catalog


def _benchmark_configuration(
    benchmark_type: ServingBenchmarkType,
    workload: ServingPerformanceWorkload,
    settings: ProductServingBenchmarkSettings,
) -> ServingBenchmarkConfiguration:
    return ServingBenchmarkConfiguration(
        benchmark_type=benchmark_type,
        endpoint=ServingPerformanceEndpoint.PRODUCT,
        workload_id=workload.workload_id,
        iterations=settings.iterations,
        warmups=settings.warmups,
        concurrency=settings.concurrency,
    )


def run_product_api_production_benchmark(
    app: FastAPI,
    workload: ServingPerformanceWorkload,
    settings: ProductServingBenchmarkSettings,
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


def run_product_service_production_benchmark(
    product_service: ProductServingService,
    workload: ServingPerformanceWorkload,
    settings: ProductServingBenchmarkSettings,
    *,
    serving_configuration: ServingConfigurationMetadata,
    benchmark_run_id: str,
) -> ServingBenchmarkRunResult:
    configuration = _benchmark_configuration(ServingBenchmarkType.SERVICE, workload, settings)
    return run_service_benchmark(
        configuration,
        workload=workload,
        product_service=product_service,
        benchmark_run_id=f"{benchmark_run_id}-svc-{workload.workload_id}",
        serving_configuration=serving_configuration,
    )


def run_product_serving_performance_suite(
    catalog: ProductCatalogReadProvider,
    *,
    catalog_parquet_path: Path | None = None,
    settings: ProductServingBenchmarkSettings | None = None,
    workloads: Sequence[ServingPerformanceWorkload] = PRODUCT_SERVING_PERFORMANCE_SUCCESS_WORKLOADS,
    benchmark_run_id: str | None = None,
) -> ProductServingPerformanceSuiteResult:
    """Warm production product stack once; benchmark successful existing-product workloads only."""
    resolved_path = catalog_parquet_path or DEFAULT_PRODUCT_CATALOG_PARQUET_PATH
    resolved_settings = settings or ProductServingBenchmarkSettings()
    dependencies = build_production_product_artifact_identifiers(catalog_parquet_path=resolved_path)
    serving_configuration = build_serving_configuration_metadata(
        artifact_identifiers=dependencies.artifact_identifiers,
    )
    product_service = create_production_product_serving_service(catalog)
    app = create_app(product_service=product_service)
    run_id = benchmark_run_id or str(uuid.uuid4())

    api_results: list[ServingBenchmarkRunResult] = []
    service_results: list[ServingBenchmarkRunResult] = []
    for workload in workloads:
        api_results.append(
            run_product_api_production_benchmark(
                app,
                workload,
                resolved_settings,
                serving_configuration=serving_configuration,
                benchmark_run_id=run_id,
            ),
        )
        service_results.append(
            run_product_service_production_benchmark(
                product_service,
                workload,
                resolved_settings,
                serving_configuration=serving_configuration,
                benchmark_run_id=run_id,
            ),
        )

    return ProductServingPerformanceSuiteResult(
        benchmark_run_id=run_id,
        recorded_at_utc=datetime.now(tz=UTC),
        dependencies=dependencies,
        settings=resolved_settings,
        api_results=tuple(api_results),
        service_results=tuple(service_results),
    )


def write_product_serving_benchmark_artifacts(
    suite: ProductServingPerformanceSuiteResult,
    output_dir: Path | None = None,
) -> Path:
    target = output_dir or DEFAULT_PRODUCT_BENCHMARK_ARTIFACT_DIR
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
        json.dumps(build_product_suite_summary_dict(suite), indent=2),
        encoding="utf-8",
    )
    report_path = target / f"{stamp}_{suite.benchmark_run_id}_report.md"
    report_path.write_text(render_product_serving_benchmark_report(suite), encoding="utf-8")
    return target


def build_product_suite_summary_dict(suite: ProductServingPerformanceSuiteResult) -> dict[str, Any]:
    return {
        "benchmark_run_id": suite.benchmark_run_id,
        "recorded_at_utc": suite.recorded_at_utc.isoformat(),
        "runner_version": BENCHMARK_RUNNER_VERSION,
        "settings": suite.settings.model_dump(),
        "dependencies": {
            "product_stack": suite.dependencies.product_stack,
            "catalog_artifact_path": suite.dependencies.catalog_artifact_path,
            "catalog_row_count": suite.dependencies.catalog_row_count,
            "artifact_identifiers": suite.dependencies.artifact_identifiers,
        },
        "workloads": [workload.workload_id for workload in PRODUCT_SERVING_PERFORMANCE_SUCCESS_WORKLOADS],
        "initialization_note": (
            "Parquet index built once via ProcessedParquetProductCatalogReadProvider; "
            "not included in per-request latency samples."
        ),
    }


def render_product_serving_benchmark_report(suite: ProductServingPerformanceSuiteResult) -> str:
    lines = [
        "# Product serving performance benchmark report",
        "",
        f"- **Run ID:** `{suite.benchmark_run_id}`",
        f"- **Recorded (UTC):** {suite.recorded_at_utc.isoformat()}",
        (
            f"- **Warmups / iterations / concurrency:** {suite.settings.warmups} / "
            f"{suite.settings.iterations} / {suite.settings.concurrency}"
        ),
        f"- **Product stack:** {suite.dependencies.product_stack}",
        f"- **Catalog artifact:** `{suite.dependencies.catalog_artifact_path}`",
        "",
        "## Workloads (latency baseline — existing products only)",
        "",
    ]
    for workload in PRODUCT_SERVING_PERFORMANCE_SUCCESS_WORKLOADS:
        product_id = workload.path_parameters.get("product_id", "")
        lines.append(f"- `{workload.workload_id}` — product `{product_id}` — {workload.description}")
    lines.extend(
        [
            "",
            (
                "Missing-product workload (`product_serving_missing_v1`) is excluded from this suite; "
                "see workload catalog documentation for expected 404 semantics."
            ),
            "",
            "## Measurements",
            "",
        ],
    )
    for label, results in (("API", suite.api_results), ("Service", suite.service_results)):
        lines.append(f"### {label} boundary")
        lines.append("")
        for result in results:
            product_id = result.workload.path_parameters.get("product_id", "")
            lines.append(f"#### `{result.workload.workload_id}` (product `{product_id}`)")
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
            "Not collected in 13.8.5 (no intrusive production instrumentation).",
            "",
            "## Limitations",
            "",
            "- Absolute latency is environment-specific.",
            "- One-time Parquet load is excluded from request samples.",
            "- API minus service latency is not reported as exact HTTP overhead.",
            "",
        ],
    )
    return "\n".join(lines)


__all__ = [
    "DEFAULT_PRODUCT_BENCHMARK_ARTIFACT_DIR",
    "DEFAULT_PRODUCT_CATALOG_PARQUET_PATH",
    "PRODUCT_SERVING_PERFORMANCE_BENCHMARK_ENV",
    "ProductProductionBenchmarkDependencies",
    "ProductServingPerformanceSuiteResult",
    "build_product_suite_summary_dict",
    "build_production_product_artifact_identifiers",
    "create_production_product_catalog_provider",
    "create_production_product_serving_service",
    "create_production_product_serving_service_from_parquet",
    "render_product_serving_benchmark_report",
    "run_product_api_production_benchmark",
    "run_product_service_production_benchmark",
    "run_product_serving_performance_suite",
    "write_product_serving_benchmark_artifacts",
]
