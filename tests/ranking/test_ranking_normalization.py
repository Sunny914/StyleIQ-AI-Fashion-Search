"""Tests for Phase 10.3 feature normalization."""

from __future__ import annotations

import math

import pytest

from productiq.ranking.feature_schema import RankingFeatures
from productiq.ranking.normalization import (
    minmax_normalize_scalar,
    normalize_feature_rows,
    normalize_features_for_query,
    rank_to_reciprocal_strength,
)
from productiq.ranking.normalization_schema import (
    CONSTANT_FEATURE_NORMALIZED_VALUE,
    NORMALIZATION_SCHEMA_VERSION,
)
from productiq.ranking.retrieval_features import extract_retrieval_features
from productiq.retrieval.contracts import RetrievalCandidate, RetrievalMethod


def _raw_features(product_id: str, *, score: float = 1.0) -> RankingFeatures:
    retrieval = RetrievalCandidate(product_id=product_id, score=score, method=RetrievalMethod.BM25)
    group = extract_retrieval_features(retrieval)
    return RankingFeatures(
        product_id=product_id,
        retrieval=group,
        matching={"matched_attribute_count": 0},
        catalog={},
    )


def test_minmax_constant_group_returns_half() -> None:
    assert minmax_normalize_scalar(3.0, group_values=[3.0, 3.0]) == pytest.approx(
        CONSTANT_FEATURE_NORMALIZED_VALUE
    )


def test_minmax_missing_value_stays_none() -> None:
    assert minmax_normalize_scalar(None, group_values=[1.0, 2.0]) is None


def test_rank_reciprocal_strength() -> None:
    assert rank_to_reciprocal_strength(2) == pytest.approx(0.5)
    assert rank_to_reciprocal_strength(None) is None


def test_binary_retrieval_flags_preserved_as_zero_one() -> None:
    row = _raw_features("P1")
    normalized = normalize_feature_rows((row,))[0]
    assert normalized.retrieval.retrieved_by_bm25 == pytest.approx(1.0)
    assert normalized.retrieval.retrieved_by_vector == pytest.approx(0.0)
    assert normalized.raw.retrieval.retrieved_by_bm25 is True


def test_continuous_features_normalized_within_query_group() -> None:
    rows = (
        _raw_features("A", score=10.0),
        _raw_features("B", score=20.0),
    )
    normalized = normalize_feature_rows(rows)
    assert normalized[0].retrieval.bm25_score == pytest.approx(0.0)
    assert normalized[1].retrieval.bm25_score == pytest.approx(1.0)
    assert normalized[0].raw.retrieval.bm25_score == pytest.approx(10.0)


def test_query_group_isolation() -> None:
    group_a = (_raw_features("A", score=1.0), _raw_features("B", score=3.0))
    group_b = (_raw_features("C", score=100.0), _raw_features("D", score=300.0))
    norm_a = normalize_features_for_query(group_a)
    norm_b = normalize_features_for_query(group_b)
    assert norm_a[0].retrieval.bm25_score == pytest.approx(0.0)
    assert norm_b[0].retrieval.bm25_score == pytest.approx(0.0)


def test_one_candidate_group_uses_constant_value() -> None:
    row = _raw_features("solo", score=5.0)
    normalized = normalize_feature_rows((row,))[0]
    assert normalized.retrieval.bm25_score == pytest.approx(CONSTANT_FEATURE_NORMALIZED_VALUE)


def test_attribute_overlap_unchanged() -> None:
    row = RankingFeatures(
        product_id="P1",
        retrieval={
            "retrieved_by_bm25": True,
            "retrieved_by_vector": False,
            "retrieved_by_both": False,
        },
        matching={"matched_attribute_count": 0, "attribute_overlap": 0.75},
        catalog={},
    )
    normalized = normalize_feature_rows((row,))[0]
    assert normalized.matching.attribute_overlap == pytest.approx(0.75)


def test_matching_missing_bool_stays_none() -> None:
    row = RankingFeatures(
        product_id="P1",
        retrieval={
            "retrieved_by_bm25": True,
            "retrieved_by_vector": False,
            "retrieved_by_both": False,
        },
        matching={"matched_attribute_count": 0, "brand_match": None},
        catalog={},
    )
    normalized = normalize_feature_rows((row,))[0]
    assert normalized.matching.brand_match is None


def test_deterministic_repeated_normalization() -> None:
    rows = (
        _raw_features("A", score=1.0),
        _raw_features("B", score=2.0),
    )
    first = normalize_feature_rows(rows)
    second = normalize_feature_rows(rows)
    assert first[0].model_dump() == second[0].model_dump()


def test_input_tuple_not_mutated() -> None:
    rows = (_raw_features("A", score=1.0), _raw_features("B", score=2.0))
    snapshot = rows
    normalize_feature_rows(rows)
    assert rows == snapshot


def test_normalized_schema_version_set() -> None:
    row = _raw_features("P1")
    normalized = normalize_feature_rows((row,))[0]
    assert normalized.normalization_schema_version == NORMALIZATION_SCHEMA_VERSION


def test_no_nan_in_normalized_output() -> None:
    rows = (
        _raw_features("A", score=1.0),
        _raw_features("B", score=4.0),
    )
    payload = normalize_feature_rows(rows)[0].model_dump()
    for value in _walk_floats(payload):
        assert math.isfinite(value)


def _walk_floats(node: object) -> list[float]:
    if isinstance(node, float):
        return [node]
    if isinstance(node, dict):
        collected: list[float] = []
        for value in node.values():
            collected.extend(_walk_floats(value))
        return collected
    if isinstance(node, list):
        collected = []
        for value in node:
            collected.extend(_walk_floats(value))
        return collected
    return []
