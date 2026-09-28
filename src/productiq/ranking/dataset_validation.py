"""Ranking dataset validation (Phase 10.3)."""

from __future__ import annotations

from productiq.exceptions.base import RankingError
from productiq.ranking.dataset_schema import RankingDataset, RankingDatasetRow


def validate_ranking_dataset_row(row: RankingDatasetRow) -> None:
    if not row.query_id.strip():
        msg = "query_id must not be empty"
        raise RankingError(msg)
    if not row.product_id.strip():
        msg = "product_id must not be empty"
        raise RankingError(msg)


def validate_ranking_dataset(dataset: RankingDataset) -> None:
    seen: set[tuple[str, str]] = set()
    feature_versions: set[str] = set()
    normalization_versions: set[str] = set()
    for row in dataset.rows:
        validate_ranking_dataset_row(row)
        key = (row.query_id, row.product_id)
        if key in seen:
            msg = f"duplicate query/product row: query_id={row.query_id!r} product_id={row.product_id!r}"
            raise RankingError(msg)
        seen.add(key)
        feature_versions.add(row.feature_schema_version)
        normalization_versions.add(row.normalization_schema_version)
        if len(feature_versions) > 1:
            msg = "inconsistent feature_schema_version across dataset rows"
            raise RankingError(msg)
        if len(normalization_versions) > 1:
            msg = "inconsistent normalization_schema_version across dataset rows"
            raise RankingError(msg)
        if row.features.product_id != row.product_id:
            msg = "feature/product identity mismatch"
            raise RankingError(msg)


__all__ = ["validate_ranking_dataset", "validate_ranking_dataset_row"]
