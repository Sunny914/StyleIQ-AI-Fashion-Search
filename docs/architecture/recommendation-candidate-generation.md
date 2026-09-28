# Phase 11.2 — Recommendation Candidate Generation

**Status:** Implemented  
**Scope:** Candidate pool generation only (no recommendation ranking)

## Why candidate generation is separate from ranking

Candidate generators produce a **deduplicated, constraint-filtered pool** with native per-source generation scores. Ranking (future) will order that pool into `RecommendationResponse`; scores must not be summed or averaged across VECTOR, BM25, and ATTRIBUTE.

## Architecture

```text
RecommendationRequest
  → seed resolution
  → VECTOR / ATTRIBUTE / BM25 generators (each ≤ candidate_pool_top_k)
  → union + provenance merge
  → seed exclusion
  → QueryFilterConstraints filtering
  → RecommendationCandidateGenerationResult
```

## Seed-product resolution

`SeedProductResolver` / `RecommendationCatalogAccess` load `ProductRepresentation` via existing catalog patterns (`PostgresSeedProductResolver`, `InMemoryRecommendationCatalog`). Missing seeds raise `CatalogValidationError`.

## Vector generator

Uses existing `VectorIndex` + seed embedding lookup (`PostgresSeedEmbeddingProvider` reads `products.embedding`). Native **cosine similarity** is stored as `candidate_generation_score` with `sources=(vector,)`. Seed is excluded from hits.

## Attribute generator

Deterministic weighted overlap on structured `ProductRepresentation` fields (`ATTRIBUTE_FIELD_WEIGHTS`). Requires matching `category_gender`. Scores are in `[0, 1]` and are **ATTRIBUTE generation scores**, not comparable to vector/BM25.

## BM25 generator

Deterministic seed lexical text via `build_seed_lexical_text` (Phase 3.5 lexical conventions). Reuses `InvertedLexicalIndex` + `BM25Scorer` without a second index. Native BM25 score preserved; provenance `bm25`.

## Candidate pool configuration

`RecommendationCandidateGenerationConfig.candidate_pool_top_k` defaults to **50** (configurable, capped by `max_candidate_pool_top_k`). Distinct from `RecommendationRequest.top_k` (final recommendation cap).

## Union / deduplication

`merge_recommendation_candidates` unions by `product_id`. `sources` is a sorted tuple of all contributing generators.

## Multi-source provenance (11.2 contract change)

`RecommendationCandidate.source` → **`sources: tuple[RecommendationCandidateSource, ...]`** (sorted by enum value). Example: `(attribute, bm25, vector)`.

## Generation-score semantics on merge

When multiple sources contribute, per-source scores are tracked internally. The exported `candidate_generation_score` uses **`MERGE_SCORE_SOURCE_PRIORITY`**: VECTOR, then BM25, then ATTRIBUTE. Scores are **not** summed or averaged.

## Seed exclusion

Applied in each generator and again after union/filtering via `exclude_seed_product`.

## Constraint filtering

`filter_recommendation_candidates` reuses `filtering_satisfies_query_constraints` with `QueryFilterConstraints` (same facet language as search).

## Empty / failure semantics

| Case | Behavior |
|------|----------|
| Invalid / missing seed | `CatalogValidationError` |
| Valid seed, no generator output | Empty candidate tuple |
| All candidates filtered | Empty tuple |
| One generator empty | Others still contribute |
| Generator failure | Default **fail-fast** (`RecommendationError`); optional `continue_on_generator_failure` |

## Determinism

Generator outputs use score-desc / `product_id` tie-breaks where applicable. Final pool sorted by `product_id`. Source tuples sorted by enum value.

## Limitations

No recommendation ranking, LTR, personalization, diversity, popularity/behavioral generators, API, cache, or evaluation.

## Future generators

`POPULARITY` and `BEHAVIORAL` remain enum placeholders for later phases.

## Code map

| Module | Role |
|--------|------|
| `candidate_generation.py` | Orchestrator |
| `generators/*` | VECTOR / ATTRIBUTE / BM25 |
| `provenance.py` | Union + score policy |
| `seed_product.py` | Seed + catalog access |
| `seed_embedding.py` | Seed vector lookup |
| `candidate_filtering.py` | Hard constraints |

## Notebook

`notebooks/data_engineering/48_recommendation_candidate_generation.ipynb`
