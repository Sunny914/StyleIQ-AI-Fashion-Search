"""Ranking evaluation diagnostics (Phase 10.6)."""

from __future__ import annotations

from productiq.ranking.evaluation.schema import RankingDiagnosticTag, RankingQueryDiagnostics
from productiq.retrieval.evaluation.metrics import (
    normalize_relevant_product_ids,
    normalize_retrieved_product_ids,
)


def build_ranking_query_diagnostics(
    *,
    judged_relevant_product_ids: tuple[str, ...] | list[str],
    candidate_pool_product_ids: tuple[str, ...] | list[str],
    evaluated_ranked_product_ids: tuple[str, ...] | list[str],
    evaluation_top_k: int,
    first_relevant_rank: int | None,
) -> RankingQueryDiagnostics:
    judged = normalize_relevant_product_ids(judged_relevant_product_ids)
    pool = frozenset(candidate_pool_product_ids)
    evaluated = normalize_retrieved_product_ids(
        evaluated_ranked_product_ids,
        max_count=evaluation_top_k,
    )
    evaluated_set = frozenset(evaluated)
    missing_from_pool = tuple(sorted(judged - pool))
    relevant_in_pool = judged & pool
    not_in_evaluated_top = tuple(sorted(relevant_in_pool - evaluated_set))

    tags: list[RankingDiagnosticTag] = []
    if missing_from_pool:
        tags.append(RankingDiagnosticTag.RELEVANT_NOT_IN_CANDIDATE_POOL)
    if relevant_in_pool and not_in_evaluated_top:
        tags.append(RankingDiagnosticTag.RELEVANT_RETRIEVED_BUT_RANKED_LOW)
    if first_relevant_rank == 1 and judged:
        tags.append(RankingDiagnosticTag.RELEVANT_RANKED_HIGH)

    return RankingQueryDiagnostics(
        diagnostic_tags=tuple(tags),
        relevant_missing_from_pool_product_ids=missing_from_pool,
        relevant_in_pool_not_in_evaluated_top_product_ids=not_in_evaluated_top,
    )


__all__ = ["build_ranking_query_diagnostics"]
