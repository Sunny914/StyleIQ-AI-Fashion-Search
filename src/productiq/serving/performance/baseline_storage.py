"""Baseline artifact storage (Phase 13.8.7)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError as PydanticValidationError

from productiq.exceptions.base import ValidationError
from productiq.serving.performance.baseline_identity import identity_from_run_result
from productiq.serving.performance.baseline_schema import (
    BaselineLookupResult,
    BaselineLookupStatus,
    BenchmarkRunIdentity,
    ServingPerformanceBaselineRecord,
)
from productiq.serving.performance.concurrency_schema import BenchmarkBoundary
from productiq.serving.performance.schema import ServingBenchmarkRunResult

PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_BASELINES_ROOT = PROJECT_ROOT / "resources" / "benchmark" / "baselines"

VALID_BASELINE_CATEGORIES = frozenset({"search", "recommendation", "product", "concurrency"})


def category_for_endpoint(endpoint_value: str) -> str:
    mapping = {
        "search": "search",
        "recommendation": "recommendation",
        "product": "product",
    }
    if endpoint_value in mapping:
        return mapping[endpoint_value]
    msg = f"unsupported baseline category for endpoint: {endpoint_value}"
    raise ValidationError(msg)


def baseline_directory(
    category: str,
    *,
    root: Path | None = None,
) -> Path:
    if category not in VALID_BASELINE_CATEGORIES:
        msg = f"invalid baseline category: {category}"
        raise ValidationError(msg)
    return (root or DEFAULT_BASELINES_ROOT) / category


def load_run_result_artifact(path: Path) -> ServingBenchmarkRunResult:
    if not path.is_file():
        msg = f"benchmark artifact not found: {path}"
        raise ValidationError(msg)
    return ServingBenchmarkRunResult.model_validate_json(path.read_text(encoding="utf-8"))


def load_baseline_record(path: Path) -> ServingPerformanceBaselineRecord:
    if not path.is_file():
        msg = f"baseline artifact not found: {path}"
        raise ValidationError(msg)
    return ServingPerformanceBaselineRecord.model_validate_json(path.read_text(encoding="utf-8"))


def pin_baseline_record(
    record: ServingPerformanceBaselineRecord,
    *,
    category: str,
    overwrite: bool = False,
    root: Path | None = None,
) -> Path:
    target_dir = baseline_directory(category, root=root)
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{record.baseline_id}.json"
    target = target_dir / filename
    if target.is_file() and not overwrite:
        msg = f"baseline already exists (use overwrite=True): {target}"
        raise ValidationError(msg)
    target.write_text(record.model_dump_json(indent=2), encoding="utf-8")
    return target


def pin_run_result_as_baseline(
    result: ServingBenchmarkRunResult,
    *,
    category: str,
    baseline_id: str | None = None,
    benchmark_boundary: BenchmarkBoundary | None = None,
    source_artifact_path: str | None = None,
    notes: str | None = None,
    overwrite: bool = False,
    root: Path | None = None,
) -> ServingPerformanceBaselineRecord:
    identity = identity_from_run_result(result, benchmark_boundary=benchmark_boundary)
    resolved_id = baseline_id or identity.storage_key()
    record = ServingPerformanceBaselineRecord(
        baseline_id=resolved_id,
        identity=identity,
        environment=result.environment,
        serving_configuration=result.serving_configuration,
        result=result,
        pinned_at_utc=datetime.now(tz=UTC),
        source_artifact_path=source_artifact_path,
        notes=notes,
    )
    pin_baseline_record(record, category=category, overwrite=overwrite, root=root)
    return record


def find_baseline_by_identity(
    identity: BenchmarkRunIdentity,
    *,
    category: str,
    root: Path | None = None,
) -> BaselineLookupResult:
    target_dir = baseline_directory(category, root=root)
    if not target_dir.is_dir():
        return BaselineLookupResult(status=BaselineLookupStatus.BASELINE_NOT_FOUND, identity=identity)
    for path in sorted(target_dir.glob("*.json")):
        try:
            record = load_baseline_record(path)
        except (ValidationError, PydanticValidationError, ValueError, OSError):
            continue
        if record.identity == identity:
            return BaselineLookupResult(
                status=BaselineLookupStatus.FOUND,
                baseline=record,
                identity=identity,
            )
    return BaselineLookupResult(status=BaselineLookupStatus.BASELINE_NOT_FOUND, identity=identity)


__all__ = [
    "DEFAULT_BASELINES_ROOT",
    "VALID_BASELINE_CATEGORIES",
    "baseline_directory",
    "category_for_endpoint",
    "find_baseline_by_identity",
    "load_baseline_record",
    "load_run_result_artifact",
    "pin_baseline_record",
    "pin_run_result_as_baseline",
]
