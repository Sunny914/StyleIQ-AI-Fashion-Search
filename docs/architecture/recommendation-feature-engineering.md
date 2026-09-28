# Phase 11.4 — Recommendation Feature Engineering

**Status:** Implemented  
**Scope:** Feature representation only (no recommendation ranking)

Phase 11.4 creates recommendation features. It does not rank recommendations.

## Lineage

```text
Phase 11.2 RecommendationCandidate
        +
Phase 11.3 ContentSimilarity
        +
RecommendationProductContext / seed filtering
        ↓
RecommendationFeatureExtractor
        ↓
RecommendationFeatures
        ↓
(optional) RecommendationFeatureMatrix for future LTR
```

## Feature groups

| Group | Source |
|-------|--------|
| `generation` | `RecommendationCandidate` provenance and native generation score |
| `similarity` | Phase 11.3 semantic / lexical components |
| `structured` | Phase 11.3 scalar / multi-value overlaps (renamed for ML readability) |
| `catalog` | `FilteringRepresentation` economics + seed-relative price deltas |

## Candidate-generation features

Binary provenance flags (`retrieved_by_vector`, `retrieved_by_attribute`, `retrieved_by_bm25`), `retrieved_by_multiple_sources`, `source_count`, and raw `candidate_generation_score`. No cross-generator normalization or weighted merge scores.

## Similarity features

`semantic_similarity` and `lexical_similarity` copied from `ContentSimilarity`. No `overall_similarity` and no weighted blends.

## Structured features

Propagated from Phase 11.3 without recomputation:

- Scalars → `brand_match`, `brand_normalized_match`, `category_gender_match`, `product_type_match`
- Multi-value Jaccard → `*_overlap` fields

## Catalog / context features

When candidate filtering is supplied: `discount_price_inr`, `original_price_inr`, `discount_amount_inr`. When seed filtering is also supplied: `discount_price_delta_from_seed_inr`, `original_price_delta_from_seed_inr`. No popularity, CTR, ratings, or behavioral fields.

## Missing-value semantics

Missing similarity signals remain `None` on `RecommendationFeatures`. They are **not** imputed to `0.0`. Matrix conversion maps `None` → `NaN` only at the matrix boundary (Phase 10 LTR convention).

## Versioning

`RECOMMENDATION_FEATURE_SCHEMA_VERSION = 11.4.0` on each `RecommendationFeatures` row. Immutable Pydantic models with `extra=forbid`.

## Feature ordering

Explicit `ORDERED_RECOMMENDATION_FEATURE_NAMES` (25 names): generation → similarity → structured → catalog. Used by `vectorize_recommendation_features` and `build_recommendation_feature_matrix`. `RECOMMENDATION_FEATURE_ORDER_VERSION = 11.4.0`.

## Matrix representation

`build_recommendation_feature_matrix` produces a dense `float64` matrix, `RecommendationFeatureSpec`, and aligned `product_ids`. Booleans encode as `1.0` / `0.0`. No query-group normalization in 11.4.

## Alignment invariants

`extract_features` requires `candidate.product_id == similarity.product_id == context.product_id`. Batch extraction rejects duplicate candidate IDs and missing similarity/context entries. Joins are by `product_id`, not positional similarity lists.

## Determinism

Stable source handling from sorted Phase 11.2 `sources`, explicit feature order, stable serialization.

## Future LTR compatibility

Feature objects preserve raw / missing semantics for Phase 11.5+ ranking and later LTR training. Normalization remains out of scope unless semantics match retrieval ranking (Phase 10.3).

## Explicit non-goals

No recommendation scoring, weighted fusion, ranking, LTR train/infer, diversity, personalization, popularity/behavioral models, evaluation, API, Redis, or BM25/vector/RRF changes.

## Limitations

- Generator rank features are not exposed (not preserved by 11.2 merge)
- Catalog features require injected `FilteringRepresentation`
- No online catalog loading inside the extractor
