"""Baseline identity helpers (Phase 13.8.7)."""

from __future__ import annotations

from productiq.exceptions.base import ValidationError
from productiq.serving.performance.baseline_schema import BenchmarkRunIdentity
from productiq.serving.performance.concurrency_schema import BenchmarkBoundary
from productiq.serving.performance.schema import (
    ServingBenchmarkRunResult,
    ServingBenchmarkType,
)


def infer_benchmark_boundary(
    benchmark_type: ServingBenchmarkType,
    *,
    explicit_boundary: BenchmarkBoundary | None = None,
) -> BenchmarkBoundary:
    if explicit_boundary is not None:
        return explicit_boundary
    if benchmark_type is ServingBenchmarkType.API:
        return "api"
    if benchmark_type is ServingBenchmarkType.SERVICE:
        return "service"
    msg = (
        "benchmark_boundary must be provided for CONCURRENCY benchmark_type results "
        "(for example when pinning a run from a concurrency sweep)."
    )
    raise ValidationError(msg)


def identity_from_run_result(
    result: ServingBenchmarkRunResult,
    *,
    benchmark_boundary: BenchmarkBoundary | None = None,
) -> BenchmarkRunIdentity:
    boundary = infer_benchmark_boundary(
        result.configuration.benchmark_type,
        explicit_boundary=benchmark_boundary,
    )
    return BenchmarkRunIdentity(
        endpoint=result.configuration.endpoint,
        workload_id=result.configuration.workload_id,
        benchmark_boundary=boundary,
        concurrency=result.configuration.concurrency,
        warmups=result.configuration.warmups,
        iterations=result.configuration.iterations,
    )


def identities_match(
    baseline: BenchmarkRunIdentity,
    current: BenchmarkRunIdentity,
) -> tuple[bool, tuple[str, ...]]:
    mismatches: list[str] = []
    if baseline.endpoint != current.endpoint:
        mismatches.append(f"endpoint: {baseline.endpoint.value} != {current.endpoint.value}")
    if baseline.workload_id != current.workload_id:
        mismatches.append(f"workload_id: {baseline.workload_id!r} != {current.workload_id!r}")
    if baseline.benchmark_boundary != current.benchmark_boundary:
        mismatches.append(
            f"benchmark_boundary: {baseline.benchmark_boundary} != {current.benchmark_boundary}",
        )
    if baseline.concurrency != current.concurrency:
        mismatches.append(f"concurrency: {baseline.concurrency} != {current.concurrency}")
    if baseline.warmups != current.warmups:
        mismatches.append(f"warmups: {baseline.warmups} != {current.warmups}")
    if baseline.iterations != current.iterations:
        mismatches.append(f"iterations: {baseline.iterations} != {current.iterations}")
    return not mismatches, tuple(mismatches)


__all__ = [
    "identities_match",
    "identity_from_run_result",
    "infer_benchmark_boundary",
]
