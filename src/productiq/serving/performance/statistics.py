"""Latency statistics helpers for serving performance benchmarks (Phase 13.8.1)."""

from __future__ import annotations

import math


def _percentile(sorted_samples: tuple[float, ...], quantile: float) -> float:
    if not sorted_samples:
        msg = "samples must not be empty"
        raise ValueError(msg)
    if quantile <= 0:
        return sorted_samples[0]
    if quantile >= 1:
        return sorted_samples[-1]
    position = (len(sorted_samples) - 1) * quantile
    lower_index = math.floor(position)
    upper_index = math.ceil(position)
    if lower_index == upper_index:
        return sorted_samples[lower_index]
    lower = sorted_samples[lower_index]
    upper = sorted_samples[upper_index]
    weight = position - lower_index
    return lower + (upper - lower) * weight


def compute_latency_statistics_ms(samples_ms: tuple[float, ...]) -> dict[str, float | int]:
    """Compute min/P50/P95/P99/max latency in milliseconds from raw samples.

    Percentiles use linear interpolation on the sorted sample (Hyndman type-7 style
    with index range ``0 .. n-1``), matching ``statistics._percentile``.
    """
    if not samples_ms:
        msg = "samples_ms must not be empty"
        raise ValueError(msg)
    for value in samples_ms:
        if not math.isfinite(value):
            msg = "latency samples must be finite"
            raise ValueError(msg)
        if value < 0:
            msg = "latency samples must be non-negative"
            raise ValueError(msg)
    ordered = tuple(sorted(samples_ms))
    return {
        "sample_count": len(ordered),
        "min_ms": ordered[0],
        "p50_ms": _percentile(ordered, 0.50),
        "p95_ms": _percentile(ordered, 0.95),
        "p99_ms": _percentile(ordered, 0.99),
        "max_ms": ordered[-1],
        "mean_ms": sum(ordered) / len(ordered),
    }


__all__ = ["compute_latency_statistics_ms"]
