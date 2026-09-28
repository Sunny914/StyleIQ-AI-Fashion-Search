"""Greedy recommendation selection after ranking (Phase 11.6)."""

from __future__ import annotations

from collections.abc import Sequence

from productiq.exceptions.base import RecommendationError
from productiq.recommendation.contracts import (
    RankedRecommendation,
    RecommendationRequest,
    RecommendationResponse,
)
from productiq.recommendation.invariants import (
    validate_positive_top_k,
    validate_recommendation_request_for_pipeline,
    validate_recommendation_response_invariants,
    validate_seed_product_excluded,
    validate_unique_recommendation_product_ids,
)
from productiq.recommendation.selection_config import RecommendationSelectionConfig
from productiq.recommendation.selection_context import RecommendationSelectionContext
from productiq.recommendation.selection_diagnostics import (
    RecommendationSelectionDecision,
    RecommendationSelectionDiagnostic,
    RecommendationSelectionRejectionReason,
    RecommendationSelectionResult,
)
from productiq.recommendation.selection_keys import diversity_brand_key, diversity_product_type_key
from productiq.retrieval.catalog_constraint_match import (
    constraints_are_active,
    filtering_satisfies_query_constraints,
)


def _validate_ranked_input_order(ranked_candidates: Sequence[RankedRecommendation]) -> None:
    if len(ranked_candidates) < 2:
        return
    for index, row in enumerate(ranked_candidates):
        expected_rank = index + 1
        if row.rank != expected_rank:
            msg = "ranked candidates must be in contiguous ascending rank order from Phase 11.5"
            raise RecommendationError(msg)


def _reject(
    row: RankedRecommendation,
    *,
    reason: RecommendationSelectionRejectionReason,
) -> RecommendationSelectionDiagnostic:
    return RecommendationSelectionDiagnostic(
        product_id=row.product_id,
        decision=RecommendationSelectionDecision.REJECTED,
        reason=reason,
        input_rank=row.rank,
        recommendation_score=row.recommendation_score,
    )


def _selected_diagnostic(row: RankedRecommendation) -> RecommendationSelectionDiagnostic:
    return RecommendationSelectionDiagnostic(
        product_id=row.product_id,
        decision=RecommendationSelectionDecision.SELECTED,
        reason=None,
        input_rank=row.rank,
        recommendation_score=row.recommendation_score,
    )


def _hard_constraint_reason(
    row: RankedRecommendation,
    *,
    context: RecommendationSelectionContext,
    config: RecommendationSelectionConfig,
    encountered_product_ids: set[str],
) -> RecommendationSelectionRejectionReason | None:
    if context.seed_product_id is not None and row.product_id == context.seed_product_id:
        return RecommendationSelectionRejectionReason.SEED_EXCLUDED
    if row.product_id in encountered_product_ids:
        return RecommendationSelectionRejectionReason.DUPLICATE_PRODUCT
    encountered_product_ids.add(row.product_id)

    constraints = context.query_constraints
    if constraints is None or not constraints_are_active(constraints):
        return None
    filtering = context.filtering_by_product_id.get(row.product_id)
    if filtering is None:
        if config.strict_constraints:
            return RecommendationSelectionRejectionReason.FILTER_METADATA_MISSING
        return None
    if not filtering_satisfies_query_constraints(filtering, constraints):
        return RecommendationSelectionRejectionReason.FILTER_CONSTRAINT
    return None


def _diversity_constraint_reason(
    *,
    brand_key: str | None,
    product_type_key: str | None,
    brand_counts: dict[str, int],
    product_type_counts: dict[str, int],
    config: RecommendationSelectionConfig,
) -> RecommendationSelectionRejectionReason | None:
    if (
        config.max_per_brand is not None
        and brand_key is not None
        and brand_counts.get(brand_key, 0) >= config.max_per_brand
    ):
        return RecommendationSelectionRejectionReason.MAX_PER_BRAND
    if (
        config.max_per_product_type is not None
        and product_type_key is not None
        and product_type_counts.get(product_type_key, 0) >= config.max_per_product_type
    ):
        return RecommendationSelectionRejectionReason.MAX_PER_PRODUCT_TYPE
    return None


def select_recommendations_with_diagnostics(
    ranked_candidates: Sequence[RankedRecommendation],
    *,
    top_k: int,
    config: RecommendationSelectionConfig | None = None,
    context: RecommendationSelectionContext | None = None,
) -> RecommendationSelectionResult:
    """Greedy selection in existing rank order without modifying scores."""
    resolved_config = config or RecommendationSelectionConfig()
    resolved_context = context or RecommendationSelectionContext()
    validate_positive_top_k(top_k)

    if not ranked_candidates:
        return RecommendationSelectionResult(selected=(), diagnostics=())

    _validate_ranked_input_order(ranked_candidates)

    selected: list[RankedRecommendation] = []
    diagnostics: list[RecommendationSelectionDiagnostic] = []
    encountered_product_ids: set[str] = set()
    brand_counts: dict[str, int] = {}
    product_type_counts: dict[str, int] = {}

    for row in ranked_candidates:
        hard_reason = _hard_constraint_reason(
            row,
            context=resolved_context,
            config=resolved_config,
            encountered_product_ids=encountered_product_ids,
        )
        if hard_reason is not None:
            diagnostics.append(_reject(row, reason=hard_reason))
            continue

        filtering = resolved_context.filtering_by_product_id.get(row.product_id)
        product = resolved_context.product_by_product_id.get(row.product_id)
        brand_key = diversity_brand_key(filtering=filtering, product=product)
        product_type_key = diversity_product_type_key(filtering=filtering, product=product)
        diversity_reason = _diversity_constraint_reason(
            brand_key=brand_key,
            product_type_key=product_type_key,
            brand_counts=brand_counts,
            product_type_counts=product_type_counts,
            config=resolved_config,
        )
        if diversity_reason is not None:
            diagnostics.append(_reject(row, reason=diversity_reason))
            continue

        if brand_key is not None:
            brand_counts[brand_key] = brand_counts.get(brand_key, 0) + 1
        if product_type_key is not None:
            product_type_counts[product_type_key] = product_type_counts.get(product_type_key, 0) + 1

        final_rank = len(selected) + 1
        selected.append(
            RankedRecommendation(
                product_id=row.product_id,
                rank=final_rank,
                recommendation_score=row.recommendation_score,
                candidate=row.candidate,
            )
        )
        diagnostics.append(_selected_diagnostic(row))
        if len(selected) >= top_k:
            break

    result_selected = tuple(selected)
    validate_unique_recommendation_product_ids(result_selected)
    if resolved_context.seed_product_id is not None:
        validate_seed_product_excluded(
            seed_product_id=resolved_context.seed_product_id,
            recommendations=result_selected,
        )
    return RecommendationSelectionResult(
        selected=result_selected,
        diagnostics=tuple(diagnostics),
    )


def select_recommendations(
    ranked_candidates: Sequence[RankedRecommendation],
    *,
    top_k: int,
    config: RecommendationSelectionConfig | None = None,
    context: RecommendationSelectionContext | None = None,
) -> tuple[RankedRecommendation, ...]:
    """Return final recommendations after hard and diversity constraints."""
    return select_recommendations_with_diagnostics(
        ranked_candidates,
        top_k=top_k,
        config=config,
        context=context,
    ).selected


def select_recommendations_for_request(
    request: RecommendationRequest,
    ranked_candidates: Sequence[RankedRecommendation],
    *,
    config: RecommendationSelectionConfig | None = None,
    context: RecommendationSelectionContext | None = None,
) -> RecommendationResponse:
    """Build a contract-valid response after selection (scores unchanged)."""
    validate_recommendation_request_for_pipeline(request)
    if context is None:
        selection_context = RecommendationSelectionContext(
            seed_product_id=request.seed_product_id,
            query_constraints=request.filters,
        )
    else:
        selection_context = context.model_copy(
            update={
                "seed_product_id": context.seed_product_id or request.seed_product_id,
                "query_constraints": context.query_constraints or request.filters,
            }
        )
    selected = select_recommendations(
        ranked_candidates,
        top_k=request.top_k,
        config=config,
        context=selection_context,
    )
    response = RecommendationResponse(
        seed_product_id=request.seed_product_id,
        recommendation_type=request.recommendation_type,
        recommendations=selected,
        requested_top_k=request.top_k,
        config=request.config,
    )
    validate_recommendation_response_invariants(response)
    return response


__all__ = [
    "select_recommendations",
    "select_recommendations_for_request",
    "select_recommendations_with_diagnostics",
]
