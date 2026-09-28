"""Ranking failure analysis builder (Phase 10.9)."""

from __future__ import annotations

from productiq.ranking.evaluation.schema import (
    RankingBenchmarkEvaluationResult,
    RankingDiagnosticTag,
    RankingQueryEvaluationResult,
)
from productiq.ranking.failure_analysis.schema import (
    RankingFailureCategory,
    RankingFailureRecord,
)
from productiq.retrieval.evaluation.dataset import LexicalRetrievalBenchmark


def _record_from_diagnostic_tag(
    row: RankingQueryEvaluationResult,
    *,
    tag: RankingDiagnosticTag,
    category: RankingFailureCategory,
    affected_stage: str,
    observed: tuple[str, ...],
    hypotheses: tuple[str, ...],
    evidence: dict[str, str | int | float | bool | None],
) -> RankingFailureRecord | None:
    if tag not in row.diagnostics.diagnostic_tags:
        return None
    return RankingFailureRecord(
        query_id=row.query_id,
        category=category,
        affected_stage=affected_stage,
        observed_facts=observed,
        diagnosis_hypotheses=hypotheses,
        evidence=evidence,
        mitigation="Review retrieval pool depth and filtering; ranking cannot promote unseen products.",
        remaining_limitation="Judged relevant set is incomplete over the full catalog.",
    )


def build_failure_records_for_query(row: RankingQueryEvaluationResult) -> tuple[RankingFailureRecord, ...]:
    records: list[RankingFailureRecord] = []
    if row.filtered_pool_candidate_count == 0:
        records.append(
            RankingFailureRecord(
                query_id=row.query_id,
                category=RankingFailureCategory.EMPTY_CANDIDATE_POOL,
                affected_stage="retrieval/filtering",
                observed_facts=(
                    f"filtered_pool_candidate_count={row.filtered_pool_candidate_count}",
                    "baseline ranking received zero candidates",
                ),
                diagnosis_hypotheses=(
                    "Hypothesis: query intent or filters removed all fused candidates.",
                ),
                evidence={"filtered_pool_candidate_count": row.filtered_pool_candidate_count},
                mitigation="Inspect retrieval intent, constraints, and catalog filter behavior.",
            )
        )
    missing_pool = _record_from_diagnostic_tag(
        row,
        tag=RankingDiagnosticTag.RELEVANT_NOT_IN_CANDIDATE_POOL,
        category=RankingFailureCategory.RELEVANT_NOT_IN_CANDIDATE_POOL,
        affected_stage="retrieval/candidate_pool",
        observed=(
            f"missing_from_pool={row.diagnostics.relevant_missing_from_pool_product_ids}",
            f"pool_size={row.filtered_pool_candidate_count}",
        ),
        hypotheses=(
            "Hypothesis: judged relevant products were not retrieved or were removed by hard filtering.",
        ),
        evidence={
            "missing_count": len(row.diagnostics.relevant_missing_from_pool_product_ids),
            "candidate_coverage": row.candidate_coverage,
        },
    )
    if missing_pool:
        records.append(missing_pool)
    ranked_low = _record_from_diagnostic_tag(
        row,
        tag=RankingDiagnosticTag.RELEVANT_RETRIEVED_BUT_RANKED_LOW,
        category=RankingFailureCategory.RELEVANT_RETRIEVED_BUT_RANKED_LOW,
        affected_stage="baseline_ranking",
        observed=(
            f"relevant_not_in_evaluated_top={row.diagnostics.relevant_in_pool_not_in_evaluated_top_product_ids}",
            f"baseline_first_relevant_rank={row.baseline.metrics.first_relevant_rank}",
        ),
        hypotheses=(
            "Hypothesis: baseline feature weights placed judged relevant products below evaluation depth.",
        ),
        evidence={"baseline_mrr": row.baseline.metrics.reciprocal_rank},
    )
    if ranked_low:
        records.append(ranked_low)
    if (
        row.diagnostics.relevant_in_pool_not_in_evaluated_top_product_ids
        and row.filtered_pool_candidate_count > 0
    ):
        records.append(
            RankingFailureRecord(
                query_id=row.query_id,
                category=RankingFailureCategory.EVALUATION_DEPTH_LIMITED,
                affected_stage="evaluation_top_k",
                observed_facts=(
                    "judged relevant IDs exist in pool but fall outside evaluated ranked depth",
                    f"pool_size={row.filtered_pool_candidate_count}",
                ),
                diagnosis_hypotheses=(
                    "Hypothesis: evaluation_top_k truncates ranked lists before all pool items are scored.",
                ),
                evidence={"filtered_pool_candidate_count": row.filtered_pool_candidate_count},
                remaining_limitation="Metrics reflect top-k truncation, not full-pool order beyond depth.",
            )
        )
    return tuple(records)


def build_ranking_failure_records(
    evaluation: RankingBenchmarkEvaluationResult,
) -> tuple[RankingFailureRecord, ...]:
    records: list[RankingFailureRecord] = []
    for row in evaluation.per_query:
        records.extend(build_failure_records_for_query(row))
    return tuple(records)


def build_ranking_failure_records_from_benchmark(
    benchmark: LexicalRetrievalBenchmark,
    evaluation: RankingBenchmarkEvaluationResult,
) -> tuple[RankingFailureRecord, ...]:
    del benchmark
    return build_ranking_failure_records(evaluation)


def ranking_failure_record_for_ltr_incompatibility(
    *,
    query_id: str,
    error_message: str,
) -> RankingFailureRecord:
    return RankingFailureRecord(
        query_id=query_id,
        category=RankingFailureCategory.LTR_ARTIFACT_INCOMPATIBLE,
        affected_stage="ltr_inference",
        observed_facts=(f"RankingError: {error_message}",),
        diagnosis_hypotheses=(
            "Hypothesis: artifact feature schema/order/policy does not match pipeline contracts.",
        ),
        evidence={},
        mitigation="Retrain or reload a compatible Phase 10.7 artifact; production baseline remains default.",
    )


__all__ = [
    "build_failure_records_for_query",
    "build_ranking_failure_records",
    "build_ranking_failure_records_from_benchmark",
    "ranking_failure_record_for_ltr_incompatibility",
]
