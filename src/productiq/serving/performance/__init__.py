"""Serving performance benchmark contracts (Phase 13.8.1)."""

from __future__ import annotations

from productiq.serving.performance.comparison import compare_serving_benchmark_runs
from productiq.serving.performance.contract_version import SERVING_PERFORMANCE_CONTRACT_VERSION
from productiq.serving.performance.executors import (
    run_api_benchmark,
    run_api_benchmark_app,
    run_service_benchmark,
)
from productiq.serving.performance.runner import (
    BENCHMARK_RUNNER_NAME,
    BENCHMARK_RUNNER_VERSION,
    run_serving_benchmark,
    run_serving_benchmark_for_workload_id,
)
from productiq.serving.performance.schema import (
    BenchmarkErrorSummary,
    LatencyStatistics,
    ServingBenchmarkComparison,
    ServingBenchmarkConfiguration,
    ServingBenchmarkRunResult,
    ServingBenchmarkType,
    ServingPerformanceEndpoint,
    ServingPerformanceWorkload,
    ThroughputStatistics,
)
from productiq.serving.performance.statistics import compute_latency_statistics_ms
from productiq.serving.performance.timing import PerfCounterTimer, ScriptedTimer
from productiq.serving.performance.workloads import (
    DEFAULT_SERVING_PERFORMANCE_WORKLOADS,
    get_serving_performance_workload,
)

__all__ = [
    "BENCHMARK_RUNNER_NAME",
    "BENCHMARK_RUNNER_VERSION",
    "DEFAULT_SERVING_PERFORMANCE_WORKLOADS",
    "SERVING_PERFORMANCE_CONTRACT_VERSION",
    "BenchmarkErrorSummary",
    "LatencyStatistics",
    "PerfCounterTimer",
    "ScriptedTimer",
    "ServingBenchmarkComparison",
    "ServingBenchmarkConfiguration",
    "ServingBenchmarkRunResult",
    "ServingBenchmarkType",
    "ServingPerformanceEndpoint",
    "ServingPerformanceWorkload",
    "ThroughputStatistics",
    "compare_serving_benchmark_runs",
    "compute_latency_statistics_ms",
    "get_serving_performance_workload",
    "run_api_benchmark",
    "run_api_benchmark_app",
    "run_service_benchmark",
    "run_serving_benchmark",
    "run_serving_benchmark_for_workload_id",
]
