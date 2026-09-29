"""Extract paired query-level metric observations (Phase 12.9)."""

from __future__ import annotations

from dataclasses import dataclass

from productiq.exceptions.base import RetrievalError
from productiq.retrieval.evaluation.search_evaluation.result_schema import (
    SearchQueryMetricResult,
    SearchVariantEvaluationResult,
)
from productiq.retrieval.evaluation.search_evaluation.statistical_schema import (
    SearchStatisticalMetricName,
)


@dataclass(frozen=True)
class PairedMetricObservationSet:
    query_ids: tuple[str, ...]
    reference_values: tuple[float, ...]
    candidate_values: tuple[float, ...]
    paired_differences: tuple[float, ...]
    total_queries: int
    eligible_queries: int
    excluded_queries: int
    exclusion_reasons: tuple[str, ...]


def per_query_metrics_by_id(
    result: SearchVariantEvaluationResult,
) -> dict[str, SearchQueryMetricResult]:
    return {row.query_id: row for row in result.per_query}


def align_query_ids(
    reference: SearchVariantEvaluationResult,
    candidate: SearchVariantEvaluationResult,
) -> tuple[str, ...]:
    ref_ids = {row.query_id for row in reference.per_query}
    cand_ids = {row.query_id for row in candidate.per_query}
    if ref_ids != cand_ids:
        missing_in_candidate = sorted(ref_ids - cand_ids)
        missing_in_reference = sorted(cand_ids - ref_ids)
        msg = (
            "reference and candidate per_query query_id sets must match exactly; "
            f"missing_in_candidate={missing_in_candidate!r} "
            f"missing_in_reference={missing_in_reference!r}"
        )
        raise RetrievalError(msg)
    return tuple(sorted(ref_ids))


def metric_value_at_k(
    row: SearchQueryMetricResult,
    metric_name: SearchStatisticalMetricName,
    k: int | None,
) -> float | None:
    if metric_name is SearchStatisticalMetricName.MRR:
        return row.reciprocal_rank
    if k is None:
        msg = f"{metric_name.value} requires k"
        raise RetrievalError(msg)
    if metric_name is SearchStatisticalMetricName.PRECISION_AT_K:
        return row.precision_at_k[k]
    if metric_name is SearchStatisticalMetricName.RECALL_AT_K:
        return row.recall_at_k[k]
    if metric_name is SearchStatisticalMetricName.HIT_RATE_AT_K:
        return row.hit_rate_at_k[k]
    if metric_name is SearchStatisticalMetricName.NDCG_AT_K:
        return row.ndcg_at_k[k]
    msg = f"unsupported metric_name {metric_name!r}"
    raise RetrievalError(msg)


def exclusion_reason_for_none(
    metric_name: SearchStatisticalMetricName,
    row: SearchQueryMetricResult,
) -> str:
    if metric_name is SearchStatisticalMetricName.RECALL_AT_K:
        if not row.recall_aggregate_eligible:
            return "recall_ineligible_no_judged_relevant_at_min_grade"
        return "recall_at_k_none"
    if metric_name is SearchStatisticalMetricName.NDCG_AT_K:
        return "ndcg_at_k_none"
    return "metric_value_none"


def build_paired_observations(
    reference: SearchVariantEvaluationResult,
    candidate: SearchVariantEvaluationResult,
    *,
    metric_name: SearchStatisticalMetricName,
    k: int | None,
) -> PairedMetricObservationSet:
    query_ids = align_query_ids(reference, candidate)
    ref_map = per_query_metrics_by_id(reference)
    cand_map = per_query_metrics_by_id(candidate)
    total = len(query_ids)
    ref_values: list[float] = []
    cand_values: list[float] = []
    diffs: list[float] = []
    eligible_ids: list[str] = []
    reasons: list[str] = []
    for query_id in query_ids:
        ref_row = ref_map[query_id]
        cand_row = cand_map[query_id]
        ref_val = metric_value_at_k(ref_row, metric_name, k)
        cand_val = metric_value_at_k(cand_row, metric_name, k)
        if ref_val is None or cand_val is None:
            if ref_val is None:
                reasons.append(f"{query_id}:{exclusion_reason_for_none(metric_name, ref_row)}")
            elif cand_val is None:
                reasons.append(f"{query_id}:{exclusion_reason_for_none(metric_name, cand_row)}")
            continue
        eligible_ids.append(query_id)
        ref_values.append(ref_val)
        cand_values.append(cand_val)
        diffs.append(cand_val - ref_val)
    excluded = total - len(eligible_ids)
    unique_reasons = tuple(sorted(set(reasons)))
    return PairedMetricObservationSet(
        query_ids=tuple(eligible_ids),
        reference_values=tuple(ref_values),
        candidate_values=tuple(cand_values),
        paired_differences=tuple(diffs),
        total_queries=total,
        eligible_queries=len(eligible_ids),
        excluded_queries=excluded,
        exclusion_reasons=unique_reasons,
    )


def mean_values(values: tuple[float, ...]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def mean_absolute_paired_difference(differences: tuple[float, ...]) -> float | None:
    if not differences:
        return None
    return sum(abs(value) for value in differences) / len(differences)


__all__ = [
    "PairedMetricObservationSet",
    "align_query_ids",
    "build_paired_observations",
    "mean_absolute_paired_difference",
    "mean_values",
    "metric_value_at_k",
    "per_query_metrics_by_id",
]
