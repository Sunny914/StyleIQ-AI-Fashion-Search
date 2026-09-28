"""Recommendation candidate generation orchestrator (Phase 11.2)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from productiq.exceptions.base import RecommendationError
from productiq.recommendation.candidate_filtering import filter_recommendation_candidates
from productiq.recommendation.contracts import (
    RecommendationCandidate,
    RecommendationCandidateGenerationResult,
    RecommendationGeneratorFailureRecord,
    RecommendationRequest,
)
from productiq.recommendation.generators.protocol import RecommendationCandidateGenerator
from productiq.recommendation.provenance import merge_recommendation_candidates
from productiq.recommendation.seed_product import RecommendationCatalogAccess
from productiq.representation.filtering import FilteringRepresentation


def exclude_seed_product(
    candidates: tuple[RecommendationCandidate, ...],
    *,
    seed_product_id: str,
) -> tuple[RecommendationCandidate, ...]:
    return tuple(row for row in candidates if row.product_id != seed_product_id)


def sort_candidate_pool_deterministically(
    candidates: tuple[RecommendationCandidate, ...],
) -> tuple[RecommendationCandidate, ...]:
    """Stable pool ordering before ranking (product_id ascending)."""
    return tuple(sorted(candidates, key=lambda row: row.product_id))


def apply_candidate_pool_top_k(
    candidates: tuple[RecommendationCandidate, ...],
    *,
    candidate_pool_top_k: int,
) -> tuple[RecommendationCandidate, ...]:
    """Cap the merged pool deterministically (preserves product_id sort from generation)."""
    if candidate_pool_top_k <= 0:
        msg = "candidate_pool_top_k must be positive"
        raise RecommendationError(msg)
    if len(candidates) <= candidate_pool_top_k:
        return candidates
    return candidates[:candidate_pool_top_k]


def generate_recommendation_candidates(
    request: RecommendationRequest,
    *,
    catalog: RecommendationCatalogAccess,
    generators: Sequence[RecommendationCandidateGenerator],
    filtering_by_product_id: Mapping[str, FilteringRepresentation],
) -> RecommendationCandidateGenerationResult:
    """Run enabled generators, union, dedupe, exclude seed, and apply hard constraints."""
    generation_config = request.config.candidate_generation
    seed_product = catalog.resolve_seed_product(request.seed_product_id)

    groups: list[tuple[RecommendationCandidate, ...]] = []
    generator_failures: list[RecommendationGeneratorFailureRecord] = []
    for generator in generators:
        generator_name = type(generator).__name__
        try:
            rows = generator.generate(request, seed_product)
        except Exception as exc:
            if generation_config.continue_on_generator_failure:
                generator_failures.append(
                    RecommendationGeneratorFailureRecord(
                        generator_name=generator_name,
                        error_message=str(exc),
                    )
                )
                continue
            msg = f"recommendation candidate generator failed: {exc}"
            raise RecommendationError(msg) from exc
        groups.append(rows)

    merged = merge_recommendation_candidates(*groups) if groups else ()
    merged = exclude_seed_product(merged, seed_product_id=request.seed_product_id)
    filtered = filter_recommendation_candidates(
        merged,
        constraints=request.filters,
        filtering_by_product_id=filtering_by_product_id,
    )
    filtered = exclude_seed_product(filtered, seed_product_id=request.seed_product_id)
    ordered = sort_candidate_pool_deterministically(filtered)

    return RecommendationCandidateGenerationResult(
        seed_product_id=request.seed_product_id,
        recommendation_type=request.recommendation_type,
        candidates=ordered,
        candidate_pool_top_k=generation_config.candidate_pool_top_k,
        config=request.config,
        generator_failures=tuple(generator_failures),
    )


__all__ = [
    "apply_candidate_pool_top_k",
    "exclude_seed_product",
    "generate_recommendation_candidates",
    "sort_candidate_pool_deterministically",
]
