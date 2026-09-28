"""Lexical retrieval evaluation orchestration (Phase 4.8)."""

from __future__ import annotations

from productiq.representation.query_contract import build_query_representation
from productiq.retrieval.contracts import RetrievalRequest, Retriever
from productiq.retrieval.evaluation.contracts import (
    AggregateMetricValues,
    LexicalRetrievalEvaluationResult,
    PerQueryMetricValues,
    QueryEvaluationResult,
)
from productiq.retrieval.evaluation.dataset import LexicalRetrievalBenchmark
from productiq.retrieval.evaluation.metrics import (
    count_relevant_in_prefix,
    macro_mean,
    mean_reciprocal_rank,
    normalize_relevant_product_ids,
    normalize_retrieved_product_ids,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
    validate_positive_k,
)
from productiq.retrieval.evaluation.schema import DEFAULT_EVALUATION_K_VALUES


class LexicalRetrievalEvaluator:
    """Evaluate any ``Retriever`` against a judged benchmark (not BM25-specific)."""

    def __init__(
        self,
        *,
        retrieval_top_k: int,
        k_values: tuple[int, ...] = DEFAULT_EVALUATION_K_VALUES,
    ) -> None:
        validate_positive_k(retrieval_top_k)
        if not k_values:
            msg = "k_values must not be empty"
            raise ValueError(msg)
        for k in k_values:
            validate_positive_k(k)
        self._retrieval_top_k = retrieval_top_k
        self._k_values = tuple(sorted(set(k_values)))

    @property
    def retrieval_top_k(self) -> int:
        return self._retrieval_top_k

    @property
    def k_values(self) -> tuple[int, ...]:
        return self._k_values

    def evaluate(
        self,
        benchmark: LexicalRetrievalBenchmark,
        retriever: Retriever,
    ) -> LexicalRetrievalEvaluationResult:
        per_query: list[QueryEvaluationResult] = []
        for evaluation_query in benchmark.queries:
            request = RetrievalRequest(
                query=build_query_representation(evaluation_query.query_text),
                top_k=self._retrieval_top_k,
            )
            response = retriever.retrieve(request)
            retrieved = normalize_retrieved_product_ids(
                tuple(candidate.product_id for candidate in response.candidates),
                max_count=self._retrieval_top_k,
            )
            relevant = normalize_relevant_product_ids(evaluation_query.relevant_product_ids)
            rr, first_rank = reciprocal_rank(retrieved, relevant)
            precision_map: dict[int, float] = {}
            recall_map: dict[int, float | None] = {}
            hits_map: dict[int, int] = {}
            for k in self._k_values:
                effective_k = min(k, self._retrieval_top_k)
                hits_map[k] = count_relevant_in_prefix(retrieved, relevant, k=effective_k)
                precision_map[k] = precision_at_k(retrieved, relevant, k=effective_k)
                recall_map[k] = recall_at_k(retrieved, relevant, k=effective_k)
            recall_eligible = len(relevant) > 0
            per_query.append(
                QueryEvaluationResult(
                    query_id=evaluation_query.query_id,
                    query_text=evaluation_query.query_text,
                    category=evaluation_query.category,
                    judged_relevant_count=len(relevant),
                    metrics=PerQueryMetricValues(
                        precision_at_k=precision_map,
                        recall_at_k=recall_map,
                        reciprocal_rank=rr,
                        recall_aggregate_eligible=recall_eligible,
                        retrieved_product_ids=retrieved,
                        relevant_hits_in_top_k=hits_map,
                        first_relevant_rank=first_rank,
                    ),
                    retrieval_candidate_count=response.candidate_count,
                )
            )
        aggregate = self._aggregate(per_query)
        return LexicalRetrievalEvaluationResult(
            benchmark_name=benchmark.benchmark_name,
            benchmark_version=benchmark.benchmark_version,
            retrieval_top_k=self._retrieval_top_k,
            k_values=self._k_values,
            per_query=tuple(per_query),
            aggregate=aggregate,
        )

    def _aggregate(self, per_query: list[QueryEvaluationResult]) -> AggregateMetricValues:
        k_values = self._k_values
        mean_precision: dict[int, float] = {}
        mean_recall: dict[int, float] = {}
        for k in k_values:
            mean_precision[k] = macro_mean(
                tuple(result.metrics.precision_at_k[k] for result in per_query)
            )
            recall_values_list: list[float] = []
            for result in per_query:
                if not result.metrics.recall_aggregate_eligible:
                    continue
                recall_value = result.metrics.recall_at_k[k]
                if recall_value is None:
                    continue
                recall_values_list.append(recall_value)
            mean_recall[k] = macro_mean(recall_values_list) if recall_values_list else 0.0
        recall_aggregate_query_count = sum(
            1 for result in per_query if result.metrics.recall_aggregate_eligible
        )
        mrr = mean_reciprocal_rank(
            tuple(result.metrics.reciprocal_rank for result in per_query)
        )
        return AggregateMetricValues(
            mean_precision_at_k=mean_precision,
            mean_recall_at_k=mean_recall,
            mrr=mrr,
            query_count=len(per_query),
            recall_aggregate_query_count=recall_aggregate_query_count,
            k_values=k_values,
        )


__all__ = ["LexicalRetrievalEvaluator"]
