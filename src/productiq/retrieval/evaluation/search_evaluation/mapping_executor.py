"""Deterministic in-memory executors for search evaluation tests and notebooks (Phase 12.4)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from productiq.retrieval.evaluation.search_evaluation.benchmark_schema import SearchEvaluationQuery
from productiq.retrieval.evaluation.search_evaluation.request_schema import (
    SearchRankedResultsForQuery,
)
from productiq.retrieval.evaluation.search_evaluation.run_context import SearchEvaluationRunContext


@dataclass(frozen=True, slots=True)
class MappingSearchEvaluationExecutor:
    """Return fixed rankings per query_id (truncated to ``execution_top_k``)."""

    rankings_by_query_id: Mapping[str, tuple[str, ...]]

    def execute_query(
        self,
        query: SearchEvaluationQuery,
        context: SearchEvaluationRunContext,
    ) -> SearchRankedResultsForQuery:
        ranking = self.rankings_by_query_id.get(query.query_id, ())
        truncated = ranking[: context.execution_top_k]
        return SearchRankedResultsForQuery(
            query_id=query.query_id,
            ranked_product_ids=truncated,
        )


__all__ = ["MappingSearchEvaluationExecutor"]
