# Phase 10.8 — LTR Inference & Baseline Comparison

**Status:** Implemented  
**Scope:** Offline LTR inference and baseline comparison (does not replace production ranking)

## Purpose

Phase 10.8 loads the Phase **10.7** LightGBM artifact, validates compatibility with the current ranking feature contracts, runs **offline LTR inference** over normalized features, and compares metrics against the Phase **10.4** deterministic baseline on the **same** filtered candidate population and relevance labels.

**10.4 remains the production baseline ranker.**

**10.8 provides offline LTR inference and comparison; it does not make LTR the production ranking path.**

## Relationship to Phase 10.4

| Path | Role |
|------|------|
| `rank_candidates` (10.4) | Production ranking in `retrieve_ranked()` |
| `rank_candidates_with_ltr` (10.8) | Offline evaluation / notebooks only |

Both rankers consume **Phase 10.3 normalized features**; neither re-implements extraction or normalization.

## Phase 10.7 artifact contract

```
<artifact_directory>/
  model.lgb
  ltr_manifest.json
```

Manifest retains training lineage (feature spec, split, training config, benchmark metadata).

## Artifact loading

- `load_ltr_model_artifact(directory)` — load model + manifest; clear errors for missing directory/files or malformed JSON
- `load_validated_ltr_artifact(directory)` — load + `validate_ltr_artifact_for_pipeline`

## Compatibility validation

`validate_ltr_artifact_for_pipeline` checks:

- `feature_schema_version` == **10.2.0**
- `normalization_schema_version` == **10.3.0**
- `feature_order_version` == **10.7.0**
- `missing_value_policy_version` == **10.7.0-native-nan** (`native_nan`)
- `feature_names` == `ORDERED_LTR_FEATURE_NAMES`
- feature dimension / LightGBM `num_feature()` consistency
- internal manifest / training_config consistency

## Feature matrix generation

Inference uses `build_inference_feature_matrix` with the artifact `LTRFeatureSpec`:

- deterministic column order from the artifact
- `None` → `NaN` (same as training)

## LTR inference

```text
RankingRequest + NormalizedRankingFeatures + LTRModelArtifact
  → feature matrix → LightGBM predict → deterministic sort → RankingResponse
```

APIs:

- `rank_candidates_with_ltr`
- `rank_candidates_with_ltr_feature_rows`

## Deterministic ranking

Sort key: **`(-ranking_score, product_id)`** via `deterministic_ranking_sort_key`.

Contiguous ranks from 1; `top_k` applied after full-pool ordering.

## Baseline vs LTR comparison

Offline APIs (`LTRBaselineBenchmarkEvaluator`, `evaluate_baseline_vs_ltr_query`, `compare_baseline_ltr_metrics`):

- same benchmark queries, filtered pool, labels, `candidate_pool_top_k`, `evaluation_top_k`, and K values as Phase 10.6
- metrics via existing `evaluate_single_query` / `aggregate_query_results`
- **delta = LTR − baseline** (no winner flags)

## Evaluation metrics

MRR, P@1/5/10/20/50, R@1/5/10/20/50 (from configured `k_values`).

## Lineage

`LTRBaselineEvaluationLineage` records benchmark identity, evaluation settings, baseline version (**10.4.0**), LTR inference version (**10.8.0**), artifact/model versions, feature/normalization/order/missing-value policy versions, and judgment metadata when present.

## Failure modes

`RankingError` for missing/corrupt artifacts, schema mismatch, product-ID misalignment, empty pools where invalid, and incompatible feature matrices.

## Limitations

- Lexical benchmark: **10 queries**, **44** judged relevant IDs — engineering demo only
- No hyperparameter tuning or production integration
- Small-data LTR must not be interpreted as production-optimal

## Production boundary

LTR is **not** wired into `retrieve_ranked()`. Phase 10.9+ may extend deployment separately.

## Notebook

`notebooks/data_engineering/45_ltr_inference_and_comparison.ipynb`

## Code map

| Module | Role |
|--------|------|
| `ranking/ltr/compatibility.py` | Pipeline compatibility checks |
| `ranking/ltr/inference.py` | Offline LTR ranker |
| `ranking/ltr/inference_config.py` | 10.8 version identifiers |
| `ranking/ltr/comparison/` | Baseline vs LTR evaluation |
