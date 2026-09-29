"""Search evaluation runner orchestration (Phase 12.4)."""

from __future__ import annotations

from typing import Protocol

from pydantic import ValidationError

from productiq.exceptions.base import RetrievalError
from productiq.retrieval.evaluation.search_evaluation.benchmark_schema import SearchEvaluationQuery
from productiq.retrieval.evaluation.search_evaluation.metrics import evaluate_search_variant_metrics
from productiq.retrieval.evaluation.search_evaluation.request_schema import (
    SearchEvaluationRequest,
    SearchRankedResultsForQuery,
)
from productiq.retrieval.evaluation.search_evaluation.result_schema import (
    SearchVariantEvaluationResult,
)
from productiq.retrieval.evaluation.search_evaluation.run_context import SearchEvaluationRunContext


class SearchEvaluationVariantExecutor(Protocol):
    """Pluggable search backend for offline evaluation (BM25, semantic, etc. via adapters)."""

    def execute_query(
        self,
        query: SearchEvaluationQuery,
        context: SearchEvaluationRunContext,
    ) -> SearchRankedResultsForQuery:
        """Return ranked product IDs for one benchmark query."""
        ...


class SearchEvaluationRunner:
    """Execute a variant on every benchmark query and compute Phase 12.3 metrics."""

    def run(
        self,
        request: SearchEvaluationRequest,
        executor: SearchEvaluationVariantExecutor,
    ) -> SearchVariantEvaluationResult:
        context = SearchEvaluationRunContext(request=request)
        benchmark = request.benchmark
        variant = request.variant
        ranked_results: list[SearchRankedResultsForQuery] = []
        seen_query_ids: set[str] = set()

        for query in sorted(benchmark.queries, key=lambda row: row.query_id):
            if query.query_id in seen_query_ids:
                msg = f"duplicate benchmark query_id {query.query_id!r}"
                raise RetrievalError(msg)
            seen_query_ids.add(query.query_id)
            ranked_row = self._execute_query(executor, query, context)
            ranked_results.append(ranked_row)

        result = evaluate_search_variant_metrics(
            benchmark,
            variant,
            ranked_results,
            metric_configuration=request.metric_configuration,
        )
        return self._apply_request_lineage(result, request)

    def _execute_query(
        self,
        executor: SearchEvaluationVariantExecutor,
        query: SearchEvaluationQuery,
        context: SearchEvaluationRunContext,
    ) -> SearchRankedResultsForQuery:
        variant = context.variant
        try:
            ranked_row = executor.execute_query(query, context)
        except RetrievalError:
            raise
        except ValidationError as exc:
            msg = (
                f"invalid ranked results for benchmark query {query.query_id!r} "
                f"(variant {variant.variant_name!r} v{variant.variant_version}): {exc}"
            )
            raise RetrievalError(msg) from exc
        except Exception as exc:
            msg = (
                f"search evaluation variant execution failed for query {query.query_id!r} "
                f"(variant {variant.variant_name!r} v{variant.variant_version}): {exc}"
            )
            raise RetrievalError(msg) from exc

        if ranked_row.query_id != query.query_id:
            msg = (
                f"variant returned query_id {ranked_row.query_id!r} "
                f"but benchmark query is {query.query_id!r}"
            )
            raise RetrievalError(msg)
        return ranked_row

    @staticmethod
    def _apply_request_lineage(
        result: SearchVariantEvaluationResult,
        request: SearchEvaluationRequest,
    ) -> SearchVariantEvaluationResult:
        lineage = result.lineage.model_copy(
            update={
                "evaluation_version": request.evaluation_version,
                "metric_configuration": request.metric_configuration,
            }
        )
        return result.model_copy(
            update={
                "evaluation_version": request.evaluation_version,
                "lineage": lineage,
            }
        )


def run_search_evaluation(
    request: SearchEvaluationRequest,
    executor: SearchEvaluationVariantExecutor,
) -> SearchVariantEvaluationResult:
    """Run one search evaluation request end-to-end (execute variant + metrics)."""
    return SearchEvaluationRunner().run(request, executor)


__all__ = [
    "SearchEvaluationRunner",
    "SearchEvaluationVariantExecutor",
    "run_search_evaluation",
]
