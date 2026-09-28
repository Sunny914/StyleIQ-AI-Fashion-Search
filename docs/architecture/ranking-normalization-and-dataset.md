# Phase 10.3 — Ranking Normalization & Dataset

**Status:** Implemented  
**Scope:** Query-group normalization and labeled dataset rows (no ranker, no LTR split)

## Why normalization

Raw Phase 10.2 features use incomparable scales (BM25 magnitude vs cosine vs INR prices). Phase 10.3 prepares **query-local** normalized signals for Phase 10.4+ while preserving raw values for debugging.

## Raw vs normalized

`NormalizedRankingFeatures` contains:

- `raw` — full `RankingFeatures` (unchanged semantics)
- `retrieval` / `matching` / `catalog` — normalized groups

## Feature-type handling

| Type | Treatment |
|------|-----------|
| Binary booleans | Cast to `0.0` / `1.0`; missing → `None` |
| `attribute_overlap` | Unchanged (already in [0, 1]) |
| Continuous retrieval scores | Min-max within query group |
| Ranks | Transform to `1/rank`, then min-max within group |
| Catalog INR fields | Cast to float, min-max within query group |
| `matched_attribute_count` | Min-max within query group |

## Query-level normalization

Statistics are computed **only** from candidates sharing the same query group passed to `normalize_feature_rows`. No cross-query global normalization.

## Constant features

When `max == min` for a group (including single-candidate groups), normalized continuous values → **`0.5`** (`CONSTANT_FEATURE_NORMALIZED_VALUE`).

## Missing values

`None` raw values remain **`None`** normalized. Never coerced to zero.

## Rank semantics

`bm25_rank` / `vector_rank` use reciprocal strength `1/rank` before min-max. Missing ranks → `None`.

## Dataset schema

- **`RankingDatasetRow`**: `query_id`, `product_id`, `features`, `relevance_label` (separate y), version fields
- **`RankingDataset`**: `metadata` + ordered `rows`

## Query grouping

Rows retain `query_id`. Groups are preserved for future Phase 10.7 grouped splits (not performed here).

## Label separation

`relevance_label` is binary `{0, 1}` from judged IDs via `binary_relevance_labels_for_products` (lexical benchmark adapter). Retrieval ranks are **not** used as labels.

## Reproducibility metadata

`RankingDatasetMetadata`:

- `dataset_version` (`10.3.0`)
- `feature_schema_version`
- `normalization_schema_version`
- optional `query_set_version`, `judgment_source_version`

## Training-serving consistency

Use the same normalization functions online per request candidate group as offline during dataset build.

## Phase relationships

| Phase | Role |
|-------|------|
| 10.4 | Baseline weighted ranker consumes normalized features |
| 10.7 | LTR training/splitting |

## API

- `normalize_features_for_query` / `normalize_feature_rows`
- `build_ranking_dataset_from_query_groups`
- `validate_ranking_dataset`

## Notebook

`notebooks/data_engineering/40_ranking_normalization_and_dataset.ipynb`
