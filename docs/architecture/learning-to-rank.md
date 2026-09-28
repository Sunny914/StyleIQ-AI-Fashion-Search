# Phase 10.7 — Learning-to-Rank

**Status:** Implemented  
**Scope:** Offline LambdaMART training artifact (does not replace production baseline)

## Objective

Train a **query-group-aware** Learning-to-Rank model on Phase **10.3** `RankingDataset` rows using judged **binary relevance labels** and **normalized features** from Phase 10.3.

Phase 10.7 produces a versioned artifact. It does **not** integrate into `retrieve_ranked()` (Phase 10.8+).

## Dataset source

- `RankingDataset` / `RankingDatasetRow` (10.3)
- Labels: `relevance_label` ∈ {0, 1} from benchmark judgments via `binary_relevance_labels_for_products`
- Features: embedded `NormalizedRankingFeatures` (not re-extracted in LTR)

## Labels

| Value | Meaning |
|-------|---------|
| 1 | Judged relevant product ID |
| 0 | Not judged relevant |

Never derived from BM25/vector/RRF/baseline scores.

## Query-group splitting

Split unit = **`query_id`**. All rows for a query stay in one partition.

Default reference split config (`LTRQuerySplitConfig`):

- `split_seed`: **42**
- `train_query_fraction`: **0.6**
- `validation_query_fraction`: **0.2**
- remainder → **test**

Recorded in artifact metadata: train/validation/test query IDs, row counts, group counts.

## Feature matrix

- Order: `ORDERED_LTR_FEATURE_NAMES` (19 fields from normalized retrieval/matching/catalog groups)
- Versions: `feature_schema_version` **10.2.0**, `normalization_schema_version` **10.3.0**
- `n_rows` = dataset rows; `n_features` = 19; labels length = `n_rows`
- Query groups: LightGBM `group` sizes sum to row count per split

## Missing-value policy

**`native_nan`** (`10.7.0-native-nan`): `None` → `NaN` in the feature matrix. LightGBM learns with missing values natively (no silent zero imputation). Policy version stored in artifact.

## Model

| Field | Value |
|-------|--------|
| Library | **LightGBM** 4.5+ |
| Objective | **`lambdarank`** |
| Metric | **`ndcg`** (eval at 1, 5, 10) |

Reference hyperparameters (fixed, not tuned):

- `learning_rate=0.05`, `num_leaves=8`, `min_data_in_leaf=1`
- `lambda_l2=1.0`, `seed=42`
- `num_boost_round=50`, `early_stopping_rounds=10` on validation

## Artifact layout

```
<artifact_dir>/
  model.lgb          # LightGBM booster
  ltr_manifest.json  # lineage + feature spec + split + config
```

Default demo path (when saved by notebook/tests): under `resources/models/` or pytest `tmp_path`.

## Production isolation

Phase **10.4** baseline remains the production ranker in `retrieve_ranked()`. LTR is offline only until Phase 10.8.

## Limitations

- Lexical benchmark: **10 queries**, **44** judged relevant IDs — engineering demo only
- No hyperparameter search, no test-set tuning
- No claim of production generalization

## Relationship to 10.8

10.8 will evaluate and optionally integrate the learned model. 10.7 stops at train + artifact + load/predict contract.

## Notebook

`notebooks/data_engineering/44_learning_to_rank.ipynb`

## Code map

| Module | Role |
|--------|------|
| `ranking/ltr/config.py` | Reference training config |
| `ranking/ltr/feature_matrix.py` | Feature order + matrix |
| `ranking/ltr/split.py` | Query-group split |
| `ranking/ltr/training.py` | `train_ltr_model` |
| `ranking/ltr/artifact.py` | Save/load |
| `ranking/ltr/predict.py` | Compatibility + predict |
