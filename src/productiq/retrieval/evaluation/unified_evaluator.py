"""Retriever-agnostic unified evaluation (Phase 4.18)."""

from __future__ import annotations

from productiq.representation.query_contract import build_query_representation
from productiq.retrieval.contracts import RetrievalRequest, Retriever
from productiq.retrieval.evaluation.contracts import PerQueryMetricValues, QueryEvaluationResult
from productiq.retrieval.evaluation.dataset import LexicalEvaluationQuery, LexicalRetrievalBenchmark
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
from productiq.retrieval.evaluation.unified_evaluation_schema import (
    CategoryEvaluationResult,
    EvaluationLineage,
    EvaluationMetrics,
    EvaluationQueryResult,
    EvaluationRequest,
    EvaluationResult,
)


def _sorted_k_values(k_values: tuple[int, ...]) -> tuple[int, ...]:
    return tuple(sorted(set(k_values)))


def evaluate_single_query(
    evaluation_query: LexicalEvaluationQuery,
    retrieved_product_ids: tuple[str, ...],
    *,
    retrieval_top_k: int,
    k_values: tuple[int, ...],
    retrieval_candidate_count: int | None = None,
) -> QueryEvaluationResult:
    """Compute per-query metrics using Phase 4.8 metric definitions."""
    validate_positive_k(retrieval_top_k)
    k_values = _sorted_k_values(k_values)
    retrieved = normalize_retrieved_product_ids(retrieved_product_ids, max_count=retrieval_top_k)
    relevant = normalize_relevant_product_ids(evaluation_query.relevant_product_ids)
    rr, first_rank = reciprocal_rank(retrieved, relevant)
    precision_map: dict[int, float] = {}
    recall_map: dict[int, float | None] = {}
    hits_map: dict[int, int] = {}
    for k in k_values:
        effective_k = min(k, retrieval_top_k)
        hits_map[k] = count_relevant_in_prefix(retrieved, relevant, k=effective_k)
        precision_map[k] = precision_at_k(retrieved, relevant, k=effective_k)
        recall_map[k] = recall_at_k(retrieved, relevant, k=effective_k)
    recall_eligible = len(relevant) > 0
    candidate_count = (
        retrieval_candidate_count if retrieval_candidate_count is not None else len(retrieved)
    )
    return QueryEvaluationResult(
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
        retrieval_candidate_count=candidate_count,
    )


def _query_result_to_unified(row: QueryEvaluationResult) -> EvaluationQueryResult:
    return EvaluationQueryResult(
        query_id=row.query_id,
        query_text=row.query_text,
        category=row.category,
        judged_relevant_count=row.judged_relevant_count,
        retrieved_product_ids=row.metrics.retrieved_product_ids,
        retrieval_candidate_count=row.retrieval_candidate_count,
        precision_at_k=row.metrics.precision_at_k,
        recall_at_k=row.metrics.recall_at_k,
        reciprocal_rank=row.metrics.reciprocal_rank,
        recall_aggregate_eligible=row.metrics.recall_aggregate_eligible,
        relevant_hits_in_top_k=row.metrics.relevant_hits_in_top_k,
        first_relevant_rank=row.metrics.first_relevant_rank,
    )


def aggregate_query_results(
    per_query: tuple[QueryEvaluationResult, ...],
    *,
    k_values: tuple[int, ...],
) -> EvaluationMetrics:
    k_values = _sorted_k_values(k_values)
    if not per_query:
        msg = "per_query must not be empty"
        raise ValueError(msg)
    mean_precision: dict[int, float] = {}
    mean_recall: dict[int, float] = {}
    for k in k_values:
        mean_precision[k] = macro_mean(
            tuple(result.metrics.precision_at_k[k] for result in per_query)
        )
        recall_values: list[float] = []
        for result in per_query:
            if not result.metrics.recall_aggregate_eligible:
                continue
            recall_value = result.metrics.recall_at_k[k]
            if recall_value is None:
                continue
            recall_values.append(recall_value)
        mean_recall[k] = macro_mean(recall_values) if recall_values else 0.0
    recall_aggregate_query_count = sum(
        1 for result in per_query if result.metrics.recall_aggregate_eligible
    )
    mrr = mean_reciprocal_rank(tuple(result.metrics.reciprocal_rank for result in per_query))
    return EvaluationMetrics(
        mean_precision_at_k=mean_precision,
        mean_recall_at_k=mean_recall,
        mrr=mrr,
        query_count=len(per_query),
        recall_aggregate_query_count=recall_aggregate_query_count,
        k_values=k_values,
    )


def aggregate_by_category(
    per_query: tuple[QueryEvaluationResult, ...],
    *,
    k_values: tuple[int, ...],
) -> tuple[CategoryEvaluationResult, ...]:
    k_values = _sorted_k_values(k_values)
    by_category: dict[str, list[QueryEvaluationResult]] = {}
    for row in per_query:
        by_category.setdefault(row.category, []).append(row)
    results: list[CategoryEvaluationResult] = []
    for category in sorted(by_category):
        rows = tuple(by_category[category])
        judged_count = sum(row.judged_relevant_count for row in rows)
        results.append(
            CategoryEvaluationResult(
                category=category,
                query_count=len(rows),
                judged_relevant_product_count=judged_count,
                metrics=aggregate_query_results(rows, k_values=k_values),
            )
        )
    return tuple(results)


def build_evaluation_result(
    *,
    benchmark: LexicalRetrievalBenchmark,
    per_query: tuple[QueryEvaluationResult, ...],
    lineage: EvaluationLineage,
    productiq_version: str = "0.1.0",
) -> EvaluationResult:
    ordered = tuple(sorted(per_query, key=lambda row: row.query_id))
    k_values = lineage.k_values
    return EvaluationResult(
        productiq_version=productiq_version,
        lineage=lineage,
        per_query=tuple(_query_result_to_unified(row) for row in ordered),
        aggregate=aggregate_query_results(ordered, k_values=k_values),
        by_category=aggregate_by_category(ordered, k_values=k_values),
    )


class UnifiedRetrievalEvaluator:
    """Evaluate any ``Retriever`` using the unified ProductIQ measurement contract."""

    def __init__(
        self,
        request: EvaluationRequest,
        *,
        lineage: EvaluationLineage | None = None,
    ) -> None:
        validate_positive_k(request.retrieval_top_k)
        self._request = request
        self._lineage_template = lineage

    @property
    def request(self) -> EvaluationRequest:
        return self._request

    def evaluate(
        self,
        benchmark: LexicalRetrievalBenchmark,
        retriever: Retriever,
        *,
        productiq_version: str = "0.1.0",
    ) -> EvaluationResult:
        per_query: list[QueryEvaluationResult] = []
        for evaluation_query in benchmark.queries:
            response = retriever.retrieve(
                RetrievalRequest(
                    query=build_query_representation(evaluation_query.query_text),
                    top_k=self._request.retrieval_top_k,
                )
            )
            retrieved = tuple(candidate.product_id for candidate in response.candidates)
            per_query.append(
                evaluate_single_query(
                    evaluation_query,
                    retrieved,
                    retrieval_top_k=self._request.retrieval_top_k,
                    k_values=self._request.k_values,
                    retrieval_candidate_count=response.candidate_count,
                )
            )
        lineage = self._build_lineage(benchmark, mode="live")
        return build_evaluation_result(
            benchmark=benchmark,
            per_query=tuple(per_query),
            lineage=lineage,
            productiq_version=productiq_version,
        )

    def evaluate_from_retrieved_by_query_id(
        self,
        benchmark: LexicalRetrievalBenchmark,
        retrieved_by_query_id: dict[str, tuple[str, ...]],
        *,
        lineage: EvaluationLineage,
        productiq_version: str = "0.1.0",
    ) -> EvaluationResult:
        per_query: list[QueryEvaluationResult] = []
        for evaluation_query in benchmark.queries:
            retrieved = retrieved_by_query_id.get(evaluation_query.query_id, ())
            per_query.append(
                evaluate_single_query(
                    evaluation_query,
                    retrieved,
                    retrieval_top_k=lineage.retrieval_top_k,
                    k_values=lineage.k_values,
                )
            )
        return build_evaluation_result(
            benchmark=benchmark,
            per_query=tuple(per_query),
            lineage=lineage,
            productiq_version=productiq_version,
        )

    def _build_lineage(
        self,
        benchmark: LexicalRetrievalBenchmark,
        *,
        mode: str,
    ) -> EvaluationLineage:
        if self._lineage_template is not None:
            return self._lineage_template
        return EvaluationLineage(
            benchmark_name=benchmark.benchmark_name,
            benchmark_version=benchmark.benchmark_version,
            system_name=self._request.system_name,
            retrieval_top_k=self._request.retrieval_top_k,
            k_values=self._request.k_values,
            evaluation_mode=mode,
            limitations=(benchmark.limitations,),
        )


def default_evaluation_request(
    system_name: str,
    *,
    retrieval_top_k: int = 50,
    k_values: tuple[int, ...] = DEFAULT_EVALUATION_K_VALUES,
    evaluation_mode: str = "artifact",
) -> EvaluationRequest:
    return EvaluationRequest(
        system_name=system_name,
        retrieval_top_k=retrieval_top_k,
        k_values=k_values,
        evaluation_mode=evaluation_mode,
    )


__all__ = [
    "UnifiedRetrievalEvaluator",
    "aggregate_by_category",
    "aggregate_query_results",
    "build_evaluation_result",
    "default_evaluation_request",
    "evaluate_single_query",
]
