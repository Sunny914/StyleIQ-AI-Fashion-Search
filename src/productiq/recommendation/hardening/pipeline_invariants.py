"""Cross-stage pipeline invariant checks (Phase 11.9)."""

from __future__ import annotations

import math
from collections.abc import Sequence

from productiq.exceptions.base import RecommendationError
from productiq.recommendation.contracts import (
    RankedRecommendation,
    RecommendationCandidate,
    RecommendationCandidateGenerationResult,
    RecommendationRequest,
    RecommendationResponse,
    RecommendationType,
)
from productiq.recommendation.feature_matrix import (
    ORDERED_RECOMMENDATION_FEATURE_NAMES,
    vectorize_recommendation_features,
)
from productiq.recommendation.feature_schema import (
    RECOMMENDATION_FEATURE_SCHEMA_VERSION,
    RecommendationFeatures,
)
from productiq.recommendation.invariants import (
    validate_recommendation_response_invariants,
    validate_seed_product_excluded,
    validate_unique_candidate_product_ids,
    validate_unique_recommendation_product_ids,
)
from productiq.recommendation.recommendation_pipeline_config import (
    validate_recommendation_pool_against_request,
)
from productiq.recommendation.selection_config import RecommendationSelectionConfig
from productiq.recommendation.selection_context import RecommendationSelectionContext
from productiq.recommendation.selection_keys import diversity_brand_key, diversity_product_type_key
from productiq.recommendation.similarity_schema import (
    CONTENT_SIMILARITY_SCHEMA_VERSION,
    ContentSimilarity,
)
from productiq.retrieval.catalog_constraint_match import (
    constraints_are_active,
    filtering_satisfies_query_constraints,
)


def validate_candidate_generation_invariants(
    result: RecommendationCandidateGenerationResult,
) -> None:
    validate_unique_candidate_product_ids(result.candidates)
    if result.seed_product_id in {row.product_id for row in result.candidates}:
        msg = "seed product must not appear in candidate pool"
        raise RecommendationError(msg)
    previous_id: str | None = None
    for candidate in result.candidates:
        if previous_id is not None and candidate.product_id < previous_id:
            msg = "candidate pool must be sorted by ascending product_id"
            raise RecommendationError(msg)
        previous_id = candidate.product_id
        if candidate.candidate_generation_score is not None and not math.isfinite(
            candidate.candidate_generation_score
        ):
            msg = "candidate_generation_score must be finite when present"
            raise RecommendationError(msg)


def validate_content_similarity_batch(
    *,
    candidates: Sequence[RecommendationCandidate],
    similarities: Sequence[ContentSimilarity],
) -> None:
    if len(candidates) != len(similarities):
        msg = "similarity batch length must match candidate batch length"
        raise RecommendationError(msg)
    for candidate, similarity in zip(candidates, similarities, strict=True):
        if candidate.product_id != similarity.product_id:
            msg = "ContentSimilarity product_id must align with candidate product_id"
            raise RecommendationError(msg)
        if similarity.content_similarity_schema_version != CONTENT_SIMILARITY_SCHEMA_VERSION:
            msg = "unexpected content similarity schema version"
            raise RecommendationError(msg)
        for field_name in ("semantic_similarity", "lexical_similarity"):
            value = getattr(similarity, field_name)
            if value is not None and not math.isfinite(value):
                msg = f"{field_name} must be finite when present"
                raise RecommendationError(msg)


def validate_recommendation_features_batch(
    *,
    candidates: Sequence[RecommendationCandidate],
    features: Sequence[RecommendationFeatures],
) -> None:
    if len(candidates) != len(features):
        msg = "feature batch length must match candidate batch length"
        raise RecommendationError(msg)
    seen: set[str] = set()
    for candidate, feature in zip(candidates, features, strict=True):
        if candidate.product_id != feature.product_id:
            msg = "RecommendationFeatures product_id must align with candidate product_id"
            raise RecommendationError(msg)
        if feature.product_id in seen:
            msg = "duplicate feature product_id in batch"
            raise RecommendationError(msg)
        seen.add(feature.product_id)
        if feature.feature_schema_version != RECOMMENDATION_FEATURE_SCHEMA_VERSION:
            msg = "unexpected recommendation feature schema version"
            raise RecommendationError(msg)
        vector = vectorize_recommendation_features(feature)
        if len(vector) != len(ORDERED_RECOMMENDATION_FEATURE_NAMES):
            msg = "feature vector length must match ordered schema"
            raise RecommendationError(msg)


def validate_ranked_recommendations_invariants(
    ranked: Sequence[RankedRecommendation],
    *,
    seed_product_id: str,
) -> None:
    validate_unique_recommendation_product_ids(tuple(ranked))
    validate_seed_product_excluded(seed_product_id=seed_product_id, recommendations=tuple(ranked))
    for index, row in enumerate(ranked, start=1):
        if row.rank != index:
            msg = "ranked recommendations must use contiguous ranks starting at 1"
            raise RecommendationError(msg)
        if not math.isfinite(row.recommendation_score):
            msg = "recommendation_score must be finite"
            raise RecommendationError(msg)


def validate_selection_output_constraints(
    response: RecommendationResponse,
    *,
    ranked_input: Sequence[RankedRecommendation],
    selection_config: RecommendationSelectionConfig | None,
    selection_context: RecommendationSelectionContext | None,
) -> None:
    """Verify scores unchanged and diversity/query constraints respected on final output."""
    ranked_by_id = {row.product_id: row for row in ranked_input}
    for row in response.recommendations:
        source = ranked_by_id.get(row.product_id)
        if source is None:
            msg = "selected recommendation must originate from ranked input"
            raise RecommendationError(msg)
        if source.recommendation_score != row.recommendation_score:
            msg = "selection must not modify recommendation_score"
            raise RecommendationError(msg)
    if selection_config is None or selection_context is None:
        return
    brand_counts: dict[str, int] = {}
    type_counts: dict[str, int] = {}
    constraints = selection_context.query_constraints
    for row in response.recommendations:
        filtering = selection_context.filtering_by_product_id.get(row.product_id)
        product = selection_context.product_by_product_id.get(row.product_id)
        if constraints is not None and constraints_are_active(constraints):
            if filtering is None:
                if selection_config.strict_constraints:
                    msg = "selected product missing filter metadata under strict constraints"
                    raise RecommendationError(msg)
            elif not filtering_satisfies_query_constraints(filtering, constraints):
                msg = "selected product violates query filter constraints"
                raise RecommendationError(msg)
        brand_key = diversity_brand_key(filtering=filtering, product=product)
        if brand_key is not None:
            brand_counts[brand_key] = brand_counts.get(brand_key, 0) + 1
            if (
                selection_config.max_per_brand is not None
                and brand_counts[brand_key] > selection_config.max_per_brand
            ):
                msg = "max_per_brand constraint violated in final output"
                raise RecommendationError(msg)
        type_key = diversity_product_type_key(filtering=filtering, product=product)
        if type_key is not None:
            type_counts[type_key] = type_counts.get(type_key, 0) + 1
            if (
                selection_config.max_per_product_type is not None
                and type_counts[type_key] > selection_config.max_per_product_type
            ):
                msg = "max_per_product_type constraint violated in final output"
                raise RecommendationError(msg)


def validate_production_pipeline_response(
    *,
    request: RecommendationRequest,
    response: RecommendationResponse,
) -> None:
    validate_recommendation_response_invariants(response)
    if response.recommendation_type is not RecommendationType.SIMILAR:
        msg = "production pipeline response must use SIMILAR recommendation type"
        raise RecommendationError(msg)
    if response.seed_product_id != request.seed_product_id:
        msg = "response seed_product_id must match request"
        raise RecommendationError(msg)
    if response.requested_top_k != request.top_k:
        msg = "response requested_top_k must match request.top_k"
        raise RecommendationError(msg)


def validate_pipeline_configuration(request: RecommendationRequest) -> None:
    pool_top_k = request.config.candidate_generation.candidate_pool_top_k
    validate_recommendation_pool_against_request(
        candidate_pool_top_k=pool_top_k,
        requested_top_k=request.top_k,
    )
    selection = request.config  # selection config is separate on pipeline
    _ = selection


def validate_pipeline_guardrail_response(
    request: RecommendationRequest,
    response: RecommendationResponse,
) -> None:
    """Strong end-to-end production guardrail used by hardening tests and pipeline."""
    validate_pipeline_configuration(request)
    validate_production_pipeline_response(request=request, response=response)


__all__ = [
    "validate_candidate_generation_invariants",
    "validate_content_similarity_batch",
    "validate_pipeline_configuration",
    "validate_pipeline_guardrail_response",
    "validate_production_pipeline_response",
    "validate_ranked_recommendations_invariants",
    "validate_recommendation_features_batch",
    "validate_selection_output_constraints",
]
