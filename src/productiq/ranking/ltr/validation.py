"""LTR dataset validation (Phase 10.7)."""

from __future__ import annotations

from productiq.exceptions.base import RankingError
from productiq.ranking.dataset_schema import RankingDataset
from productiq.ranking.dataset_validation import validate_ranking_dataset


def validate_ltr_training_dataset(dataset: RankingDataset) -> None:
    validate_ranking_dataset(dataset)
    if not dataset.rows:
        msg = "LTR training dataset must contain rows"
        raise RankingError(msg)
    query_ids = {row.query_id for row in dataset.rows}
    if len(query_ids) < 3:
        msg = "LTR training requires at least 3 query groups"
        raise RankingError(msg)
    for row in dataset.rows:
        if row.relevance_label is None:
            msg = (
                f"missing relevance_label for query_id={row.query_id!r} "
                f"product_id={row.product_id!r}"
            )
            raise RankingError(msg)
        if row.relevance_label not in (0, 1):
            msg = "relevance_label must be binary 0 or 1"
            raise RankingError(msg)


__all__ = ["validate_ltr_training_dataset"]
