# Phase 10.2 — Ranking Features

**Status:** Implemented  
**Scope:** Raw feature extraction only (no scoring, normalization, LTR, or retrieval)

## Purpose

Convert an explicit ranking candidate plus query and injected product context into immutable **`RankingFeatures`** for Phase 10.3+ rankers.

```text
RankingRequest + RankingProductContext (per candidate)
        ↓
extract_features / extract_features_for_request
        ↓
RankingFeatures
```

## Pipeline position

Hard filtering (Phase 4.19 production retrieval) completes **before** ranking. Feature extraction does not remove candidates or access PostgreSQL.

## Feature taxonomy

| Group | Model | Source |
|-------|--------|--------|
| Retrieval | `RetrievalFeatureGroup` | `RetrievalCandidate` |
| Matching | `MatchingFeatureGroup` | `QueryRepresentation.constraints` vs `ProductRepresentation` |
| Catalog | `CatalogFeatureGroup` | Optional `FilteringRepresentation` on context |

Schema version: **`RANKING_FEATURE_SCHEMA_VERSION`** (`10.2.0`).

## Retrieval features

Projected from existing retrieval fields only:

| Feature | Retrieval field |
|---------|-----------------|
| `bm25_score` | `bm25_score` |
| `bm25_rank` | `bm25_rank` |
| `vector_similarity` | `vector_score` |
| `vector_rank` | `vector_rank` |
| `rrf_score` | `fusion_score` |
| `retrieved_by_bm25` | provenance |
| `retrieved_by_vector` | provenance |
| `retrieved_by_both` | both provenance flags |

Missing values remain **`None`** (not coerced to zero).

For single-method retrieval rows, native score lives on ``RetrievalCandidate.score`` when ``bm25_score`` / ``vector_score`` are unset; the extractor copies that value into ``bm25_score`` or ``vector_similarity`` respectively (aligned with Phase 4.2 score semantics, not a recomputation).

**Not implemented:** recomputed BM25, vector similarity, or RRF.

## Query–product matching features

Structured query-side values come from **`QueryFilterConstraints`** on the request query (ProductIQ does not embed brand/color in `QueryRepresentation` outside constraints).

| Feature | Semantics |
|---------|-----------|
| `brand_match` | Uses `brand_normalized` if set, else `brand`; exact match to product scalars |
| `color_match` | All constraint colors ∈ product `color` list |
| `product_type_match` | Scalar equality |
| `category_gender_match` | Scalar equality |
| `material_match` | All constraint materials ∈ product list |
| `matched_attribute_count` | Count of **true** matches among specified facets above |
| `attribute_overlap` | `matched_attribute_count / N` where **N** is count of specified facets among brand/category_gender/product_type/color/material |
| `constraint_match` | `filtering_satisfies_query_constraints` when filtering context supplied; facet-only evaluation when price bounds absent; **`None`** when price bounds set but no filtering context |

Individual match booleans are **`None`** when that constraint facet is unspecified.

### attribute_overlap when N = 0

No structured constraints → **`attribute_overlap = None`**, `matched_attribute_count = 0`.

## Catalog features

Requires injected **`FilteringRepresentation`** on `RankingProductContext`:

- `discount_price_inr`
- `original_price_inr`
- `discount_amount_inr` (`original - discount`, clamped at 0)

Without filtering context, catalog fields are **`None`**. No database lookups.

**Not implemented:** popularity, CTR, inventory, ratings, or other business signals.

## Product context

```python
RankingProductContext(
    product_id=...,
    product=ProductRepresentation,
    filtering=FilteringRepresentation | None,
)
```

Callers (future ranking service) must supply catalog fields explicitly after retrieval.

## Missing-value semantics

- Optional floats: **`None`** if absent at retrieval layer
- Optional match flags: **`None`** if query facet not specified
- Catalog: **`None`** without filtering context

## constraint_match vs hard filtering

Hard filtering already enforced in production retrieval. `constraint_match` is a **diagnostic ranking feature**, not a second filter.

## Deferred to later phases

| Phase | Responsibility |
|-------|----------------|
| 10.3 | Normalization / baseline scoring formula |
| 10.4 | Feature weights |
| 10.5+ | LTR training and evaluation |

Raw features are not normalized in 10.2.

## Training / inference consistency

Use the same extractor (`extract_features`) online and offline. Inject the same `ProductRepresentation` / `FilteringRepresentation` sources used at serving time (no hidden DB in the extractor).

## Code map

| Module | Role |
|--------|------|
| `feature_schema.py` | `RankingFeatures` groups |
| `retrieval_features.py` | Retrieval projection |
| `matching_features.py` | Constraint vs product matching |
| `catalog_features.py` | Price/discount raw values |
| `product_context.py` | Injected catalog view |
| `feature_extractor.py` | Top-level API |

## Notebook

`notebooks/data_engineering/39_ranking_features.ipynb`

## Omissions

- No query parsing beyond existing `QueryRepresentation`
- No features from retrieval candidate metadata dict beyond typed retrieval scores
- Price-based matching requires filtering context for `constraint_match`
