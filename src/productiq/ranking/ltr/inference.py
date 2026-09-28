"""Offline LTR inference ranker (Phase 10.8)."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

from productiq.exceptions.base import RankingError
from productiq.ranking.baseline_ranker import _align_candidates_and_features, _require_feature_row
from productiq.ranking.config import RankingConfig
from productiq.ranking.contracts import (
    RankedCandidate,
    RankingCandidate,
    RankingRequest,
    RankingResponse,
)
from productiq.ranking.invariants import (
    apply_ranking_top_k,
    deterministic_ranking_sort_key,
    validate_ranking_request_for_ranker,
    validate_ranking_response_invariants,
    validate_unique_ranking_product_ids,
)
from productiq.ranking.ltr.artifact import LTRModelArtifact
from productiq.ranking.ltr.compatibility import validate_ltr_artifact_for_pipeline
from productiq.ranking.ltr.feature_matrix import build_inference_feature_matrix
from productiq.ranking.ltr.inference_config import LTR_INFERENCE_VERSION
from productiq.ranking.ltr.predict import predict_ltr_scores
from productiq.ranking.normalization_schema import NormalizedRankingFeatures


def rank_candidates_with_ltr(
    *,
    request: RankingRequest,
    normalized_features_by_product_id: Mapping[str, NormalizedRankingFeatures],
    artifact: LTRModelArtifact,
    validate_artifact: bool = True,
    inference_version: str = LTR_INFERENCE_VERSION,
) -> RankingResponse:
    """Rank pre-filtered candidates using a loaded Phase 10.7 LTR artifact."""
    validate_ranking_request_for_ranker(request)
    if validate_artifact:
        validate_ltr_artifact_for_pipeline(artifact)
    validate_unique_ranking_product_ids(request.candidates)
    if not request.candidates:
        response = RankingResponse(
            ranked_candidates=(),
            requested_top_k=request.top_k,
            config=RankingConfig(ranking_version=inference_version),
        )
        validate_ranking_response_invariants(response)
        return response
    ordered_features = tuple(
        _require_feature_row(normalized_features_by_product_id, candidate.product_id)
        for candidate in request.candidates
    )
    pairs = _align_candidates_and_features(request.candidates, ordered_features)
    feature_matrix = build_inference_feature_matrix(
        tuple(features for _, features in pairs),
        expected_spec=artifact.metadata.feature_spec,
        missing_policy=artifact.metadata.training_config.missing_value_policy,
    )
    scores = predict_ltr_scores(artifact, feature_matrix)
    if scores.shape[0] != len(pairs):
        msg = "LTR score count must match candidate count"
        raise RankingError(msg)
    scored: list[tuple[RankingCandidate, float]] = []
    for index, (candidate, _features) in enumerate(pairs):
        score = float(scores[index])
        if not math.isfinite(score):
            msg = f"LTR score must be finite for product_id={candidate.product_id!r}"
            raise RankingError(msg)
        scored.append((candidate, score))
    sort_config = RankingConfig(
        ranking_version=inference_version,
        tie_break_key=request.config.tie_break_key,
    )
    scored.sort(
        key=lambda row: deterministic_ranking_sort_key(
            ranking_score=row[1],
            product_id=row[0].product_id,
            config=sort_config,
        )
    )
    ranked: list[RankedCandidate] = []
    for index, (candidate, score) in enumerate(scored, start=1):
        ranked.append(
            RankedCandidate(
                product_id=candidate.product_id,
                rank=index,
                ranking_score=score,
                candidate=candidate,
            )
        )
    trimmed = apply_ranking_top_k(tuple(ranked), top_k=request.top_k)
    response = RankingResponse(
        ranked_candidates=trimmed,
        requested_top_k=request.top_k,
        config=sort_config,
    )
    validate_ranking_response_invariants(response)
    return response


def rank_candidates_with_ltr_feature_rows(
    *,
    request: RankingRequest,
    normalized_features: Sequence[NormalizedRankingFeatures],
    artifact: LTRModelArtifact,
    validate_artifact: bool = True,
    inference_version: str = LTR_INFERENCE_VERSION,
) -> RankingResponse:
    feature_ids = [row.product_id for row in normalized_features]
    if len(feature_ids) != len(set(feature_ids)):
        msg = "normalized features must have unique product_id values"
        raise RankingError(msg)
    feature_map = {row.product_id: row for row in normalized_features}
    return rank_candidates_with_ltr(
        request=request,
        normalized_features_by_product_id=feature_map,
        artifact=artifact,
        validate_artifact=validate_artifact,
        inference_version=inference_version,
    )


__all__ = [
    "rank_candidates_with_ltr",
    "rank_candidates_with_ltr_feature_rows",
]
