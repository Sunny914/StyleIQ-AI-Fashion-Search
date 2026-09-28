"""Tests for Phase 11.1 recommendation contracts."""

from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from productiq.exceptions import RecommendationError
from productiq.recommendation.config import (
    DEFAULT_MAX_RECOMMENDATION_TOP_K,
    DEFAULT_RECOMMENDATION_CONTRACT_VERSION,
    RecommendationConfig,
)
from productiq.recommendation.contracts import (
    IMPLEMENTED_RECOMMENDATION_TYPES,
    SUPPORTED_RECOMMENDATION_TYPES,
    RankedRecommendation,
    RecommendationCandidate,
    RecommendationCandidateSource,
    RecommendationRequest,
    RecommendationResponse,
    RecommendationType,
    recommendation_request_to_dict,
)
from productiq.recommendation.invariants import (
    apply_recommendation_top_k,
    deterministic_recommendation_sort_key,
    recommendation_output_limit,
    validate_recommendation_response_invariants,
    validate_recommendation_type_implemented,
    validate_seed_product_excluded,
)
from productiq.representation.query_contract import QueryFilterConstraints


def _candidate(
    product_id: str,
    *,
    score: float | None = 0.5,
    source: RecommendationCandidateSource = RecommendationCandidateSource.VECTOR,
) -> RecommendationCandidate:
    return RecommendationCandidate(
        product_id=product_id,
        candidate_generation_score=score,
        source=source,
    )


def _ranked(
    product_id: str,
    rank: int,
    score: float,
    *,
    with_candidate: bool = True,
) -> RankedRecommendation:
    candidate = _candidate(product_id, score=score * 0.9) if with_candidate else None
    return RankedRecommendation(
        product_id=product_id,
        rank=rank,
        recommendation_score=score,
        candidate=candidate,
    )


def test_recommendation_request_valid() -> None:
    request = RecommendationRequest(
        seed_product_id="P123",
        recommendation_type=RecommendationType.SIMILAR,
        top_k=10,
        filters=QueryFilterConstraints(category_gender="Women"),
    )
    assert request.seed_product_id == "P123"
    assert request.recommendation_type is RecommendationType.SIMILAR


@pytest.mark.parametrize("bad_seed", ["", "   "])
def test_recommendation_request_rejects_empty_seed(bad_seed: str) -> None:
    with pytest.raises(ValidationError):
        RecommendationRequest(
            seed_product_id=bad_seed,
            recommendation_type=RecommendationType.SIMILAR,
            top_k=5,
        )


def test_recommendation_request_rejects_invalid_recommendation_type() -> None:
    with pytest.raises(ValidationError):
        RecommendationRequest(
            seed_product_id="P1",
            recommendation_type="unknown_mode",  # type: ignore[arg-type]
            top_k=5,
        )


@pytest.mark.parametrize("invalid_top_k", [0, -2])
def test_recommendation_request_rejects_invalid_top_k(invalid_top_k: int) -> None:
    with pytest.raises(ValidationError):
        RecommendationRequest(
            seed_product_id="P1",
            recommendation_type=RecommendationType.ALTERNATIVE,
            top_k=invalid_top_k,
        )


def test_recommendation_request_boundary_top_k_at_max() -> None:
    config = RecommendationConfig(max_top_k=25)
    request = RecommendationRequest(
        seed_product_id="P1",
        recommendation_type=RecommendationType.COMPLEMENTARY,
        top_k=25,
        config=config,
    )
    assert request.top_k == 25


def test_recommendation_request_rejects_top_k_above_config_max() -> None:
    config = RecommendationConfig(max_top_k=10)
    with pytest.raises(ValidationError, match="max_top_k"):
        RecommendationRequest(
            seed_product_id="P1",
            recommendation_type=RecommendationType.SIMILAR,
            top_k=11,
            config=config,
        )


def test_recommendation_request_is_frozen() -> None:
    request = RecommendationRequest(
        seed_product_id="P1",
        recommendation_type=RecommendationType.SIMILAR,
        top_k=3,
    )
    with pytest.raises(ValidationError):
        request.top_k = 5  # type: ignore[misc]


def test_recommendation_request_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        RecommendationRequest(
            seed_product_id="P1",
            recommendation_type=RecommendationType.SIMILAR,
            top_k=3,
            retrieval_query="shoes",  # type: ignore[call-arg]
        )


def test_supported_vs_implemented_recommendation_types() -> None:
    assert RecommendationType.SIMILAR in SUPPORTED_RECOMMENDATION_TYPES
    assert IMPLEMENTED_RECOMMENDATION_TYPES == frozenset()


def test_validate_recommendation_type_implemented_raises_in_phase_11_1() -> None:
    with pytest.raises(RecommendationError, match="not implemented"):
        validate_recommendation_type_implemented(RecommendationType.SIMILAR)


def test_recommendation_candidate_valid() -> None:
    candidate = _candidate("P9", source=RecommendationCandidateSource.BM25)
    assert candidate.source is RecommendationCandidateSource.BM25
    assert candidate.candidate_generation_score == pytest.approx(0.5)


@pytest.mark.parametrize("bad_product_id", ["", "  "])
def test_recommendation_candidate_rejects_empty_product_id(bad_product_id: str) -> None:
    with pytest.raises(ValidationError):
        RecommendationCandidate(
            product_id=bad_product_id,
            source=RecommendationCandidateSource.VECTOR,
        )


@pytest.mark.parametrize("bad_score", [math.nan, math.inf, -math.inf])
def test_recommendation_candidate_rejects_non_finite_generation_score(bad_score: float) -> None:
    with pytest.raises(ValidationError):
        RecommendationCandidate(
            product_id="P1",
            candidate_generation_score=bad_score,
            source=RecommendationCandidateSource.VECTOR,
        )


def test_recommendation_candidate_allows_missing_generation_score() -> None:
    candidate = RecommendationCandidate(
        product_id="P1",
        candidate_generation_score=None,
        source=RecommendationCandidateSource.POPULARITY,
    )
    assert candidate.candidate_generation_score is None


def test_recommendation_candidate_is_frozen() -> None:
    candidate = _candidate("P1")
    with pytest.raises(ValidationError):
        candidate.product_id = "P2"  # type: ignore[misc]


def test_ranked_recommendation_valid() -> None:
    row = _ranked("P2", rank=1, score=0.91)
    assert row.recommendation_score == pytest.approx(0.91)


def test_ranked_recommendation_rejects_mismatched_candidate() -> None:
    with pytest.raises(ValidationError, match="must match candidate"):
        RankedRecommendation(
            product_id="P1",
            rank=1,
            recommendation_score=0.5,
            candidate=_candidate("P2"),
        )


@pytest.mark.parametrize("bad_score", [math.nan, math.inf])
def test_ranked_recommendation_rejects_non_finite_score(bad_score: float) -> None:
    with pytest.raises(ValidationError):
        RankedRecommendation(
            product_id="P1",
            rank=1,
            recommendation_score=bad_score,
            candidate=_candidate("P1"),
        )


def test_recommendation_response_valid() -> None:
    response = RecommendationResponse(
        seed_product_id="P123",
        recommendation_type=RecommendationType.SIMILAR,
        recommendations=(
            _ranked("P200", rank=1, score=0.9),
            _ranked("P201", rank=2, score=0.8),
        ),
        requested_top_k=10,
        config=RecommendationConfig(),
    )
    assert response.returned_recommendation_count == 2


def test_recommendation_response_rejects_non_contiguous_ranks() -> None:
    with pytest.raises(ValidationError, match="contiguous"):
        RecommendationResponse(
            seed_product_id="P123",
            recommendation_type=RecommendationType.SIMILAR,
            recommendations=(_ranked("P200", rank=1, score=0.9), _ranked("P201", rank=3, score=0.8)),
            requested_top_k=10,
        )


def test_recommendation_response_rejects_duplicate_ranks() -> None:
    with pytest.raises(ValidationError, match="contiguous"):
        RecommendationResponse(
            seed_product_id="P123",
            recommendation_type=RecommendationType.SIMILAR,
            recommendations=(_ranked("P200", rank=1, score=0.9), _ranked("P201", rank=1, score=0.8)),
            requested_top_k=10,
        )


def test_recommendation_response_rejects_duplicate_product_ids() -> None:
    with pytest.raises(ValidationError, match="duplicate product_id"):
        RecommendationResponse(
            seed_product_id="P123",
            recommendation_type=RecommendationType.SIMILAR,
            recommendations=(_ranked("P200", rank=1, score=0.9), _ranked("P200", rank=2, score=0.8)),
            requested_top_k=10,
        )


def test_recommendation_response_rejects_seed_product_in_results() -> None:
    with pytest.raises(ValidationError, match="seed product"):
        RecommendationResponse(
            seed_product_id="P123",
            recommendation_type=RecommendationType.SIMILAR,
            recommendations=(_ranked("P123", rank=1, score=0.9),),
            requested_top_k=5,
        )


def test_recommendation_response_rejects_excess_rows_for_top_k() -> None:
    rows = (_ranked("P1", rank=1, score=1.0), _ranked("P2", rank=2, score=0.9))
    with pytest.raises(ValidationError, match="requested_top_k"):
        RecommendationResponse(
            seed_product_id="P123",
            recommendation_type=RecommendationType.SIMILAR,
            recommendations=rows,
            requested_top_k=1,
        )


def test_recommendation_response_is_frozen() -> None:
    response = RecommendationResponse(
        seed_product_id="P123",
        recommendation_type=RecommendationType.SIMILAR,
        recommendations=(),
        requested_top_k=5,
    )
    with pytest.raises(ValidationError):
        response.requested_top_k = 10  # type: ignore[misc]


def test_validate_seed_product_exclusion_invariant() -> None:
    rows = (_ranked("P123", rank=1, score=0.5),)
    with pytest.raises(RecommendationError, match="seed product"):
        validate_seed_product_excluded(seed_product_id="P123", recommendations=rows)


def test_deterministic_recommendation_sort_key() -> None:
    config = RecommendationConfig()
    key_a = deterministic_recommendation_sort_key(
        recommendation_score=0.5,
        product_id="A",
        config=config,
    )
    key_b = deterministic_recommendation_sort_key(
        recommendation_score=0.5,
        product_id="B",
        config=config,
    )
    assert key_a < key_b


def test_validate_recommendation_response_invariants_enforces_score_order() -> None:
    response = RecommendationResponse(
        seed_product_id="P123",
        recommendation_type=RecommendationType.SIMILAR,
        recommendations=(_ranked("P1", rank=1, score=0.2), _ranked("P2", rank=2, score=0.9)),
        requested_top_k=5,
    )
    with pytest.raises(RecommendationError, match="descending recommendation_score"):
        validate_recommendation_response_invariants(response)


def test_validate_recommendation_response_invariants_enforces_tie_break() -> None:
    response = RecommendationResponse(
        seed_product_id="P123",
        recommendation_type=RecommendationType.SIMILAR,
        recommendations=(
            RankedRecommendation(
                product_id="B",
                rank=1,
                recommendation_score=0.5,
                candidate=_candidate("B"),
            ),
            RankedRecommendation(
                product_id="A",
                rank=2,
                recommendation_score=0.5,
                candidate=_candidate("A"),
            ),
        ),
        requested_top_k=5,
    )
    with pytest.raises(RecommendationError, match="ascending product_id"):
        validate_recommendation_response_invariants(response)


def test_validate_recommendation_response_invariants_accepts_deterministic_output() -> None:
    response = RecommendationResponse(
        seed_product_id="P123",
        recommendation_type=RecommendationType.SIMILAR,
        recommendations=(
            RankedRecommendation(
                product_id="A",
                rank=1,
                recommendation_score=0.5,
                candidate=_candidate("A"),
            ),
            RankedRecommendation(
                product_id="B",
                rank=2,
                recommendation_score=0.5,
                candidate=_candidate("B"),
            ),
        ),
        requested_top_k=5,
    )
    validate_recommendation_response_invariants(response)


def test_recommendation_output_limit_and_apply_top_k() -> None:
    rows = tuple(_ranked(f"P{index}", rank=index, score=float(index)) for index in range(1, 5))
    assert recommendation_output_limit(recommendation_count=4, top_k=2) == 2
    trimmed = apply_recommendation_top_k(rows, top_k=2)
    assert len(trimmed) == 2
    assert rows == tuple(_ranked(f"P{index}", rank=index, score=float(index)) for index in range(1, 5))


def test_recommendation_config_defaults() -> None:
    config = RecommendationConfig()
    assert config.recommendation_contract_version == DEFAULT_RECOMMENDATION_CONTRACT_VERSION
    assert config.max_top_k == DEFAULT_MAX_RECOMMENDATION_TOP_K


def test_recommendation_request_to_dict() -> None:
    request = RecommendationRequest(
        seed_product_id="P1",
        recommendation_type=RecommendationType.PERSONALIZED,
        top_k=3,
    )
    payload = recommendation_request_to_dict(request)
    assert payload["recommendation_type"] == "personalized"
    assert payload["top_k"] == 3
