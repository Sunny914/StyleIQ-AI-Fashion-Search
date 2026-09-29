"""Search evaluation run context (Phase 12.4)."""

from __future__ import annotations

from dataclasses import dataclass

from productiq.retrieval.evaluation.search_evaluation.benchmark_schema import (
    SearchEvaluationBenchmark,
)
from productiq.retrieval.evaluation.search_evaluation.request_schema import (
    SearchEvaluationRequest,
    SearchEvaluationVariant,
    SearchMetricConfiguration,
)


@dataclass(frozen=True, slots=True)
class SearchEvaluationRunContext:
    """Immutable inputs passed to a variant executor for one evaluation run."""

    request: SearchEvaluationRequest

    @property
    def benchmark(self) -> SearchEvaluationBenchmark:
        return self.request.benchmark

    @property
    def variant(self) -> SearchEvaluationVariant:
        return self.request.variant

    @property
    def metric_configuration(self) -> SearchMetricConfiguration:
        return self.request.metric_configuration

    @property
    def execution_top_k(self) -> int:
        return self.request.metric_configuration.execution_top_k


__all__ = ["SearchEvaluationRunContext"]
