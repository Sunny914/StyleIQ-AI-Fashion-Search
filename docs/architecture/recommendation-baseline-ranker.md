# Phase 11.5 — Baseline Recommendation Ranker

**Status:** Implemented  
**Scope:** Deterministic weighted-sum ranking only (not LTR)

The 11.5 ranker is a deterministic baseline. Its weights are hand-authored configuration and are not learned parameters.

## 11.4 → 11.5 boundary

Phase 11.4 produces factual `RecommendationFeatures`. Phase 11.5 consumes those features only—it does not recompute similarity, BM25, Jaccard, or candidate generation scores.

## Scoring equation

```text
recommendation_score = Σ (weight_i × feature_value_i)
```

Binary provenance flags encode as `1.0` / `0.0` at scoring time. Missing weighted features contribute `weight × missing_feature_contribution` (default **0.0**). **`RecommendationFeatures` objects are not mutated.**

## Baseline weights (11.5.0)

| Feature | Weight |
|---------|--------|
| `similarity.semantic_similarity` | 0.20 |
| `similarity.lexical_similarity` | 0.10 |
| `generation.retrieved_by_multiple_sources` | 0.05 |
| `generation.retrieved_by_vector` | 0.03 |
| `generation.retrieved_by_attribute` | 0.03 |
| `generation.retrieved_by_bm25` | 0.03 |
| `structured.brand_match` | 0.12 |
| `structured.brand_normalized_match` | 0.03 |
| `structured.category_gender_match` | 0.08 |
| `structured.product_type_match` | 0.10 |
| `structured.color_overlap` | 0.08 |
| `structured.pattern_overlap` | 0.03 |
| `structured.material_overlap` | 0.04 |
| `structured.fit_overlap` | 0.03 |
| `structured.sleeve_overlap` | 0.02 |
| `structured.neckline_overlap` | 0.02 |
| `structured.product_features_overlap` | 0.03 |
| `structured.style_attributes_overlap` | 0.03 |

**Not weighted:** `candidate_generation_score`, `source_count`, and all catalog INR fields.

## Raw price exclusion

Catalog monetary fields remain on `RecommendationFeatures` for future experiments but receive **zero weight** in 11.5 so large INR magnitudes cannot dominate the baseline.

## Missing-value semantics

Feature `None` → zero score contribution (default policy). Feature objects retain `None`.

## No renormalization

Weights are **not** rescaled when other features are missing. A candidate with only semantic similarity `1.0` scores `0.20`, not `1.0`.

## Finite-score validation

Non-finite scores raise `RecommendationError` during scoring. `RankedRecommendation` rejects non-finite `recommendation_score`.

## Deterministic ordering

Sort key: `(-recommendation_score, product_id)` (ascending sort). Ties break on ascending `product_id`.

## Top-k

Score all eligible rows → sort → truncate → assign contiguous ranks `1..k`.

## Explainability

`BaselineRecommendationScoreBreakdown` exposes per-feature `feature_value`, `weight`, and `contribution`. Contributions sum to the final score within floating-point tolerance.

## Versioning

`BaselineRecommendationRankerConfig.ranker_version = 11.5.0`.

## Future LTR

Phase 11.5 is a transparent baseline. Learned rankers (LightGBM / LTR) are out of scope; they may consume the same feature order and matrix conventions later.

## Explicit non-goals

No LightGBM, LTR training/inference, evaluation, diversity, MMR, personalization, popularity/behavioral models, API, Redis, or weight tuning.

## Limitations

- Hand-authored weights are not quality claims  
- Lexical (BM25) and semantic scales are combined linearly without calibration  
- Seed must be excluded upstream or via `seed_product_id` filtering in the ranker  
