"""Ranking dataset construction (Phase 10.3)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from productiq.exceptions.base import RankingError
from productiq.ranking.dataset_schema import (
    RANKING_DATASET_VERSION,
    RankingDataset,
    RankingDatasetMetadata,
    RankingDatasetRow,
)
from productiq.ranking.dataset_validation import validate_ranking_dataset
from productiq.ranking.feature_schema import RANKING_FEATURE_SCHEMA_VERSION, RankingFeatures
from productiq.ranking.normalization import normalize_feature_rows
from productiq.ranking.normalization_schema import NORMALIZATION_SCHEMA_VERSION


@dataclass(frozen=True)
class RankingDatasetQueryGroup:
    """One query's raw feature rows plus optional judged relevance labels."""

    query_id: str
    features: tuple[RankingFeatures, ...]
    relevance_label_by_product_id: Mapping[str, int] | None = None


def build_ranking_dataset_from_query_groups(
    groups: tuple[RankingDatasetQueryGroup, ...],
    *,
    query_set_version: str | None = None,
    judgment_source_version: str | None = None,
    require_labels: bool = False,
) -> RankingDataset:
    """Normalize per query group and attach labels without retrieval side effects."""
    rows: list[RankingDatasetRow] = []
    for group in groups:
        if not group.query_id.strip():
            msg = "query_id must not be empty"
            raise RankingError(msg)
        normalized_rows = normalize_feature_rows(group.features)
        for normalized in normalized_rows:
            label: int | None = None
            if group.relevance_label_by_product_id is not None:
                if normalized.product_id not in group.relevance_label_by_product_id:
                    if require_labels:
                        msg = (
                            f"missing relevance label for product_id={normalized.product_id!r} "
                            f"query_id={group.query_id!r}"
                        )
                        raise RankingError(msg)
                else:
                    label = group.relevance_label_by_product_id[normalized.product_id]
            elif require_labels:
                msg = f"relevance labels required for query_id={group.query_id!r}"
                raise RankingError(msg)
            rows.append(
                RankingDatasetRow(
                    query_id=group.query_id,
                    product_id=normalized.product_id,
                    features=normalized,
                    relevance_label=label,
                    feature_schema_version=normalized.feature_schema_version,
                    normalization_schema_version=normalized.normalization_schema_version,
                )
            )
    metadata = RankingDatasetMetadata(
        dataset_version=RANKING_DATASET_VERSION,
        feature_schema_version=rows[0].feature_schema_version if rows else RANKING_FEATURE_SCHEMA_VERSION,
        normalization_schema_version=NORMALIZATION_SCHEMA_VERSION,
        query_set_version=query_set_version,
        judgment_source_version=judgment_source_version,
    )
    dataset = RankingDataset(metadata=metadata, rows=tuple(rows))
    validate_ranking_dataset(dataset)
    return dataset


__all__ = [
    "RankingDatasetQueryGroup",
    "build_ranking_dataset_from_query_groups",
]
