"""Map ProductIQ Retriever implementations to the search evaluation executor protocol (Phase 12.4)."""

from __future__ import annotations

from dataclasses import dataclass

from productiq.representation.query_contract import build_query_representation
from productiq.retrieval.contracts import RetrievalRequest, Retriever
from productiq.retrieval.evaluation.search_evaluation.benchmark_schema import SearchEvaluationQuery
from productiq.retrieval.evaluation.search_evaluation.metrics import (
    validate_search_ranked_product_ids,
)
from productiq.retrieval.evaluation.search_evaluation.request_schema import (
    SearchRankedResultsForQuery,
)
from productiq.retrieval.evaluation.search_evaluation.run_context import SearchEvaluationRunContext


@dataclass(frozen=True, slots=True)
class RetrieverSearchEvaluationExecutor:
    """Generic adapter: any ``Retriever`` can back a search evaluation variant."""

    retriever: Retriever

    def execute_query(
        self,
        query: SearchEvaluationQuery,
        context: SearchEvaluationRunContext,
    ) -> SearchRankedResultsForQuery:
        response = self.retriever.retrieve(
            RetrievalRequest(
                query=build_query_representation(query.query_text),
                top_k=context.execution_top_k,
            )
        )
        ranked_product_ids = validate_search_ranked_product_ids(
            tuple(candidate.product_id for candidate in response.candidates)
        )
        return SearchRankedResultsForQuery(
            query_id=query.query_id,
            ranked_product_ids=ranked_product_ids,
        )


__all__ = ["RetrieverSearchEvaluationExecutor"]
