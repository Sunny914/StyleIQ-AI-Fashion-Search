"""Query-group dataset splitting for LTR (Phase 10.7)."""

from __future__ import annotations

import random

from pydantic import BaseModel, ConfigDict, Field, model_validator

from productiq.exceptions.base import RankingError
from productiq.ranking.dataset_schema import RankingDataset, RankingDatasetRow
from productiq.ranking.ltr.config import LTRQuerySplitConfig


class QueryGroupSplit(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    split_seed: int
    train_query_ids: tuple[str, ...]
    validation_query_ids: tuple[str, ...]
    test_query_ids: tuple[str, ...]
    train_row_count: int = Field(ge=0)
    validation_row_count: int = Field(ge=0)
    test_row_count: int = Field(ge=0)
    train_group_count: int = Field(ge=0)
    validation_group_count: int = Field(ge=0)
    test_group_count: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_disjoint(self) -> QueryGroupSplit:
        train = set(self.train_query_ids)
        val = set(self.validation_query_ids)
        test = set(self.test_query_ids)
        if train & val or train & test or val & test:
            msg = "train/validation/test query_id sets must be disjoint"
            raise ValueError(msg)
        return self


def unique_query_ids_in_dataset(dataset: RankingDataset) -> tuple[str, ...]:
    seen: list[str] = []
    known: set[str] = set()
    for row in dataset.rows:
        if row.query_id not in known:
            known.add(row.query_id)
            seen.append(row.query_id)
    return tuple(seen)


def split_queries_for_ltr(
    query_ids: tuple[str, ...],
    *,
    config: LTRQuerySplitConfig,
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    unique = tuple(sorted(set(query_ids)))
    if len(unique) < 3:
        msg = "LTR query-group split requires at least 3 unique query_id values"
        raise RankingError(msg)
    shuffled = list(unique)
    random.Random(config.split_seed).shuffle(shuffled)
    n = len(shuffled)
    n_train = max(1, int(n * config.train_query_fraction))
    n_val = max(1, int(n * config.validation_query_fraction))
    if n_train + n_val >= n:
        n_train = max(1, n - 2)
        n_val = 1
    train = tuple(sorted(shuffled[:n_train]))
    val = tuple(sorted(shuffled[n_train : n_train + n_val]))
    test = tuple(sorted(shuffled[n_train + n_val :]))
    if not test:
        msg = "test query split must be non-empty"
        raise RankingError(msg)
    return train, val, test


def split_ranking_dataset_by_query(
    dataset: RankingDataset,
    *,
    config: LTRQuerySplitConfig,
) -> tuple[QueryGroupSplit, tuple[RankingDataset, ...]]:
    query_ids = unique_query_ids_in_dataset(dataset)
    train_ids, val_ids, test_ids = split_queries_for_ltr(query_ids, config=config)
    partitions: list[list[RankingDatasetRow]] = [[], [], []]
    id_sets = (set(train_ids), set(val_ids), set(test_ids))
    for row in dataset.rows:
        if row.query_id in id_sets[0]:
            partitions[0].append(row)
        elif row.query_id in id_sets[1]:
            partitions[1].append(row)
        elif row.query_id in id_sets[2]:
            partitions[2].append(row)
        else:
            msg = f"row query_id not assigned to any split: {row.query_id!r}"
            raise RankingError(msg)
    split = QueryGroupSplit(
        split_seed=config.split_seed,
        train_query_ids=train_ids,
        validation_query_ids=val_ids,
        test_query_ids=test_ids,
        train_row_count=len(partitions[0]),
        validation_row_count=len(partitions[1]),
        test_row_count=len(partitions[2]),
        train_group_count=len(train_ids),
        validation_group_count=len(val_ids),
        test_group_count=len(test_ids),
    )
    subsets: tuple[RankingDataset, RankingDataset, RankingDataset] = (
        RankingDataset(metadata=dataset.metadata, rows=tuple(partitions[0])),
        RankingDataset(metadata=dataset.metadata, rows=tuple(partitions[1])),
        RankingDataset(metadata=dataset.metadata, rows=tuple(partitions[2])),
    )
    return split, subsets


__all__ = [
    "QueryGroupSplit",
    "split_queries_for_ltr",
    "split_ranking_dataset_by_query",
    "unique_query_ids_in_dataset",
]
