"""Monotonic timing for serving benchmarks (Phase 13.8.2)."""

from __future__ import annotations

import time
from typing import Protocol


class MonotonicTimer(Protocol):
    """Injectable timer for deterministic benchmark tests."""

    def perf_counter(self) -> float: ...


class PerfCounterTimer:
    def perf_counter(self) -> float:
        return time.perf_counter()


class ScriptedTimer:
    """Returns scripted elapsed deltas across paired perf_counter calls."""

    def __init__(self, elapsed_seconds: tuple[float, ...]) -> None:
        self._elapsed = iter(elapsed_seconds)
        self._anchor = 0.0

    def perf_counter(self) -> float:
        try:
            delta = next(self._elapsed)
        except StopIteration:
            delta = 0.0
        self._anchor += delta
        return self._anchor


def elapsed_ms(start: float, end: float) -> float:
    elapsed = (end - start) * 1000.0
    if not (elapsed >= 0.0 and elapsed < float("inf")):
        msg = "elapsed duration must be finite and non-negative"
        raise ValueError(msg)
    return elapsed


__all__ = ["MonotonicTimer", "PerfCounterTimer", "ScriptedTimer", "elapsed_ms"]
