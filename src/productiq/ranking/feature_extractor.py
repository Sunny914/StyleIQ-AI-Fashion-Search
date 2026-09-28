"""Ranking feature extraction orchestration (Phase 10.2)."""

from __future__ import annotations

from collections.abc import Mapping

from productiq.exceptions.base import RankingError
from productiq.ranking.catalog_features import extract_catalog_features
from productiq.ranking.contracts import RankingCandidate, RankingRequest
from productiq.ranking.feature_schema import RankingFeatures
from productiq.ranking.matching_features import extract_matching_features
from productiq.ranking.product_context import RankingProductContext
from productiq.ranking.retrieval_features import extract_retrieval_features
from productiq.representation.query_contract import QueryRepresentation


def extract_features(
    *,
    query: QueryRepresentation,
    candidate: RankingCandidate,
    product_context: RankingProductContext,
) -> RankingFeatures:
    """Extract raw ranking features for one candidate (deterministic, no ranking)."""
    if candidate.product_id != product_context.product_id:
        msg = "candidate.product_id must match product_context.product_id"
        raise RankingError(msg)
    retrieval = extract_retrieval_features(candidate.retrieval)
    matching = extract_matching_features(
        query,
        product_context.product,
        filtering=product_context.filtering,
    )
    catalog = extract_catalog_features(product_context.filtering)
    return RankingFeatures(
        product_id=candidate.product_id,
        retrieval=retrieval,
        matching=matching,
        catalog=catalog,
    )


def extract_features_for_request(
    request: RankingRequest,
    *,
    product_context_by_id: Mapping[str, RankingProductContext],
) -> tuple[RankingFeatures, ...]:
    """Extract features for each candidate, preserving request order."""
    features: list[RankingFeatures] = []
    for candidate in request.candidates:
        context = product_context_by_id.get(candidate.product_id)
        if context is None:
            msg = f"missing RankingProductContext for product_id {candidate.product_id!r}"
            raise RankingError(msg)
        features.append(
            extract_features(
                query=request.query,
                candidate=candidate,
                product_context=context,
            )
        )
    return tuple(features)


__all__ = ["extract_features", "extract_features_for_request"]
