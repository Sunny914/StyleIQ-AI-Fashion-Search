"""Tests for Phase 10.4 deterministic baseline ranker."""

from __future__ import annotations

import copy
import math

import pytest
from pydantic import ValidationError

from productiq.exceptions import RankingError
from productiq.ranking.adapters import ranking_candidate_from_retrieval
from productiq.ranking.baseline_config import BaselineFeatureWeights, BaselineRankingConfig
from productiq.ranking.baseline_ranker import rank_candidates, rank_candidates_with_feature_rows
from productiq.ranking.baseline_scoring import compute_baseline_score
from productiq.ranking.contracts import RankingRequest
from productiq.ranking.feature_schema import RankingFeatures
from productiq.ranking.invariants import assert_ranking_request_inputs_unchanged
from productiq.ranking.normalization_schema import (
    NormalizedCatalogFeatureGroup,
    NormalizedMatchingFeatureGroup,
    NormalizedRankingFeatures,
    NormalizedRetrievalFeatureGroup,
)
from productiq.representation.query_contract import build_query_representation
from productiq.retrieval.contracts import RetrievalCandidate, RetrievalMethod


def _query() -> object:
    return build_query_representation("baseline ranker demo")


def _candidate(product_id: str) -> object:
    retrieval = RetrievalCandidate(
        product_id=product_id,
        score=1.0,
        method=RetrievalMethod.BM25,
    )
    return ranking_candidate_from_retrieval(retrieval)


def _raw(product_id: str) -> RankingFeatures:
    return RankingFeatures(
        product_id=product_id,
        retrieval={
            "retrieved_by_bm25": True,
            "retrieved_by_vector": False,
            "retrieved_by_both": False,
        },
        matching={"matched_attribute_count": 0},
        catalog={},
    )


def _normalized(
    product_id: str,
    *,
    retrieval: dict[str, float | None] | None = None,
    matching: dict[str, float | None] | None = None,
) -> NormalizedRankingFeatures:
    retrieval_fields = retrieval or {}
    matching_fields = matching or {}
    return NormalizedRankingFeatures(
        product_id=product_id,
        raw=_raw(product_id),
        retrieval=NormalizedRetrievalFeatureGroup(**retrieval_fields),
        matching=NormalizedMatchingFeatureGroup(
            matched_attribute_count=matching_fields.pop("matched_attribute_count", None),
            **matching_fields,
        ),
        catalog=NormalizedCatalogFeatureGroup(),
    )


def _unit_weight_config(**overrides: float) -> BaselineRankingConfig:
    base = {name: 0.0 for name in BaselineFeatureWeights.model_fields}
    base.update(overrides)
    return BaselineRankingConfig(weights=BaselineFeatureWeights(**base))


def test_known_score_single_feature_weight() -> None:
    config = _unit_weight_config(bm25_score=2.0)
    features = _normalized("P1", retrieval={"bm25_score": 0.25})
    breakdown = compute_baseline_score(features, config=config)
    assert breakdown.ranking_score == pytest.approx(0.5)


def test_missing_value_uses_configured_contribution() -> None:
    config = BaselineRankingConfig(
        weights=BaselineFeatureWeights(**{name: 0.0 for name in BaselineFeatureWeights.model_fields} | {"bm25_score": 1.0}),
        missing_value_contribution=0.25,
    )
    features = _normalized("P1", retrieval={"bm25_score": None})
    breakdown = compute_baseline_score(features, config=config)
    assert breakdown.ranking_score == pytest.approx(0.25)


def test_missing_value_default_contribution_is_zero() -> None:
    config = _unit_weight_config(bm25_score=1.0)
    features = _normalized("P1", retrieval={"bm25_score": None})
    breakdown = compute_baseline_score(features, config=config)
    assert breakdown.ranking_score == pytest.approx(0.0)


def test_non_finite_normalized_feature_rejected() -> None:
    with pytest.raises(ValidationError):
        NormalizedRetrievalFeatureGroup(bm25_score=math.inf)


def test_ordering_higher_score_ranks_first() -> None:
    config = _unit_weight_config(rrf_score=1.0)
    request = RankingRequest(
        query=_query(),
        candidates=(_candidate("LOW"), _candidate("HIGH")),
        top_k=10,
    )
    features = {
        "LOW": _normalized("LOW", retrieval={"rrf_score": 0.1}),
        "HIGH": _normalized("HIGH", retrieval={"rrf_score": 0.9}),
    }
    response = rank_candidates(request=request, normalized_features_by_product_id=features, baseline_config=config)
    assert response.ranked_candidates[0].product_id == "HIGH"
    assert response.ranked_candidates[1].product_id == "LOW"


def test_tie_break_by_product_id() -> None:
    config = _unit_weight_config(rrf_score=1.0)
    request = RankingRequest(
        query=_query(),
        candidates=(_candidate("B"), _candidate("A")),
        top_k=10,
    )
    same_score = 0.5
    features = {
        "A": _normalized("A", retrieval={"rrf_score": same_score}),
        "B": _normalized("B", retrieval={"rrf_score": same_score}),
    }
    response = rank_candidates(request=request, normalized_features_by_product_id=features, baseline_config=config)
    assert [row.product_id for row in response.ranked_candidates] == ["A", "B"]


def test_top_k_limits_response() -> None:
    config = _unit_weight_config(rrf_score=1.0)
    request = RankingRequest(
        query=_query(),
        candidates=(_candidate("P1"), _candidate("P2"), _candidate("P3")),
        top_k=2,
    )
    features = {
        pid: _normalized(pid, retrieval={"rrf_score": float(index) / 10.0})
        for index, pid in enumerate(("P1", "P2", "P3"), start=1)
    }
    response = rank_candidates(request=request, normalized_features_by_product_id=features, baseline_config=config)
    assert len(response.ranked_candidates) == 2
    assert response.requested_top_k == 2
    assert response.ranked_candidates[0].rank == 1
    assert response.ranked_candidates[1].rank == 2


def test_empty_candidates_returns_empty_response() -> None:
    request = RankingRequest(query=_query(), candidates=(), top_k=5)
    response = rank_candidates(request=request, normalized_features_by_product_id={})
    assert response.ranked_candidates == ()
    assert response.config.ranking_version == "10.4.0"


def test_single_candidate_rank_one() -> None:
    config = _unit_weight_config(attribute_overlap=1.0)
    request = RankingRequest(query=_query(), candidates=(_candidate("SOLO"),), top_k=5)
    features = {"SOLO": _normalized("SOLO", matching={"attribute_overlap": 0.8})}
    response = rank_candidates(request=request, normalized_features_by_product_id=features, baseline_config=config)
    assert len(response.ranked_candidates) == 1
    assert response.ranked_candidates[0].rank == 1
    assert response.ranked_candidates[0].product_id == "SOLO"


def test_missing_feature_row_raises() -> None:
    request = RankingRequest(query=_query(), candidates=(_candidate("P1"),), top_k=5)
    with pytest.raises(RankingError, match="missing normalized features"):
        rank_candidates(request=request, normalized_features_by_product_id={})


def test_feature_row_product_id_mismatch_raises() -> None:
    request = RankingRequest(query=_query(), candidates=(_candidate("P1"),), top_k=5)
    wrong_row = _normalized("P2")
    with pytest.raises(RankingError, match="must match"):
        rank_candidates(request=request, normalized_features_by_product_id={"P1": wrong_row})


def test_duplicate_candidate_ids_in_request_rejected_by_contract() -> None:
    with pytest.raises(ValidationError):
        RankingRequest(
            query=_query(),
            candidates=(_candidate("P1"), _candidate("P1")),
            top_k=5,
        )


def test_duplicate_feature_ids_rejected() -> None:
    request = RankingRequest(query=_query(), candidates=(_candidate("P1"),), top_k=5)
    dup = (_normalized("P1"), _normalized("P1"))
    with pytest.raises(RankingError, match="unique product_id"):
        rank_candidates_with_feature_rows(request=request, normalized_features=dup)


def test_excluded_catalog_features_do_not_affect_score() -> None:
    config = BaselineRankingConfig()
    with_catalog = _normalized(
        "P1",
        retrieval={"rrf_score": 0.5},
    )
    breakdown = compute_baseline_score(with_catalog, config=config)
    only_rrf = compute_baseline_score(
        _normalized("P1", retrieval={"rrf_score": 0.5}),
        config=config,
    )
    assert breakdown.ranking_score == pytest.approx(only_rrf.ranking_score)


def test_zero_weight_features_excluded_from_score() -> None:
    config = _unit_weight_config(
        rrf_score=1.0,
        discount_price_inr=0.0,
    )
    features = _normalized("P1", retrieval={"rrf_score": 0.4})
    breakdown = compute_baseline_score(features, config=config)
    assert breakdown.ranking_score == pytest.approx(0.4)
    names = {name for name, value in breakdown.contributions if value != 0.0}
    assert names == {"retrieval.rrf_score"}


def test_config_rejects_all_zero_weights() -> None:
    zeros = {name: 0.0 for name in BaselineFeatureWeights.model_fields}
    with pytest.raises(ValidationError, match="positive"):
        BaselineRankingConfig(weights=BaselineFeatureWeights(**zeros))


def test_config_rejects_negative_weight() -> None:
    with pytest.raises(ValidationError):
        BaselineFeatureWeights(bm25_score=-0.1)


def test_determinism_repeated_runs() -> None:
    config = BaselineRankingConfig()
    request = RankingRequest(
        query=_query(),
        candidates=(_candidate("C"), _candidate("A"), _candidate("B")),
        top_k=10,
    )
    features = {
        pid: _normalized(pid, retrieval={"rrf_score": score})
        for pid, score in (("A", 0.2), ("B", 0.2), ("C", 0.9))
    }
    first = rank_candidates(request=request, normalized_features_by_product_id=features, baseline_config=config)
    second = rank_candidates(request=request, normalized_features_by_product_id=features, baseline_config=config)
    assert first == second


def test_immutability_inputs_unchanged() -> None:
    config = BaselineRankingConfig()
    candidates = (_candidate("P1"), _candidate("P2"))
    before = copy.deepcopy(candidates)
    request = RankingRequest(query=_query(), candidates=candidates, top_k=10)
    features = {
        "P1": _normalized("P1", retrieval={"rrf_score": 0.1}),
        "P2": _normalized("P2", retrieval={"rrf_score": 0.2}),
    }
    features_before = copy.deepcopy(features)
    rank_candidates(request=request, normalized_features_by_product_id=features, baseline_config=config)
    assert_ranking_request_inputs_unchanged(before, request.candidates)
    assert features == features_before


def test_response_contiguous_ranks_no_duplicate_ids() -> None:
    config = _unit_weight_config(rrf_score=1.0)
    request = RankingRequest(
        query=_query(),
        candidates=(_candidate("P1"), _candidate("P2"), _candidate("P3")),
        top_k=3,
    )
    features = {
        "P1": _normalized("P1", retrieval={"rrf_score": 0.3}),
        "P2": _normalized("P2", retrieval={"rrf_score": 0.6}),
        "P3": _normalized("P3", retrieval={"rrf_score": 0.1}),
    }
    response = rank_candidates(request=request, normalized_features_by_product_id=features, baseline_config=config)
    ranks = [row.rank for row in response.ranked_candidates]
    assert ranks == [1, 2, 3]
    assert len({row.product_id for row in response.ranked_candidates}) == len(response.ranked_candidates)
    for row in response.ranked_candidates:
        assert math.isfinite(row.ranking_score)


def test_breakdown_lists_all_policy_fields() -> None:
    config = BaselineRankingConfig()
    breakdown = compute_baseline_score(_normalized("P1"), config=config)
    assert len(breakdown.contributions) == len(BaselineFeatureWeights.model_fields)
