# Phase 11.8 — Recommendation Pipeline

**Status:** Implemented  
**Scope:** Application-level orchestration only (no HTTP, no new ranking logic)

Phase 11.8 composes the recommendation components into an application-level pipeline. It does **not** implement the FastAPI HTTP serving layer (Phase 13).

## Purpose

Provide a single deterministic entry point:

```text
RecommendationRequest
  → validation + implemented-type enforcement
  → seed resolution
  → 11.2 candidate generation
  → 11.3 content similarity
  → 11.4 feature extraction
  → 11.5 baseline ranking (pool depth)
  → 11.6 selection (final top_k)
  → RecommendationResponse
```

Search (`RetrievalRequest` → production retrieval → search ranking) remains a **separate** flow.

## Implemented recommendation types

`IMPLEMENTED_RECOMMENDATION_TYPES` exposes **`SIMILAR` only** for the production path. Requests for `ALTERNATIVE`, `COMPLEMENTARY`, or `PERSONALIZED` raise `RecommendationError` — there is **no silent fallback**.

## Dependency injection

`RecommendationPipeline` is a frozen dataclass accepting:

| Dependency | Role |
|------------|------|
| `catalog` | Seed resolution + attribute generator catalog |
| `generators` | Phase 11.2 candidate generators |
| `similarity_engine` | Phase 11.3 |
| `ranker` | Phase 11.5 baseline ranker |
| `product_context_provider` | Batch candidate product + filtering context |
| `filtering_by_product_id` | Constraint filtering during candidate generation |
| `selection_config` | Optional Phase 11.6 limits |
| `ranker_config` | Optional override of ranker weights |

No DI framework; no hidden global singletons.

## Seed resolution

Uses `RecommendationCatalogAccess.resolve_seed_product`. Missing seeds raise `CatalogValidationError` (unchanged from 11.2).

## Candidate generation

Calls `generate_recommendation_candidates` without duplicating generator logic. Merged pool is capped with `apply_candidate_pool_top_k` using the deterministic product_id ordering from 11.2.

## Context loading

`RecommendationProductContextProvider.load_candidate_context` loads **all candidate IDs in one batch** (in-memory or PostgreSQL `IN` query). Used for similarity (`ProductRepresentation`) and feature extraction (`RecommendationProductContext`).

## Similarity, features, ranking, selection

Each stage delegates to the existing module:

- `ContentSimilarityEngine.compute_for_candidates`
- `extract_features_for_candidates`
- `rank_recommendations` with `top_k = candidate_pool_top_k`
- `select_recommendations_for_request` with `top_k = request.top_k`

Ranking weights and missing-value policy remain inside 11.5. Selection greedy logic remains inside 11.6.

## top_k semantics

| Setting | Meaning |
|---------|---------|
| `request.top_k` | Final recommendations after selection |
| `config.candidate_generation.candidate_pool_top_k` | Pool depth for generation + ranking input |
| Validation | `candidate_pool_top_k >= request.top_k` (same rule as production retrieval) |

Example: pool 50 → rank up to 50 → select final 10.

## Empty results

Zero candidates after generation/filtering returns a valid `RecommendationResponse` with `recommendations=()` — no popularity fallback, no random fill.

## Shortfalls

When 11.6 constraints block slots, the response may contain fewer than `requested_top_k` rows. Constraints are **not** relaxed to fill the list.

## Error propagation

Stage-specific wrappers are **not** used to mask underlying errors. `CatalogValidationError`, `SemanticRetrievalError`, `RecommendationError`, etc. propagate unchanged. `RecommendationPipelineStage` enum documents stage names for future observability only.

## Determinism

Same request + catalog snapshot + configuration → identical response. No randomness or timestamps in response identity.

## Optional execution metadata

`recommend_with_metadata` returns `RecommendationPipelineExecutionMetadata` with `candidate_count`, `ranked_count`, and `selected_count` (counts only, no timings in 11.8).

## Production vs experimental

Production path: 11.2 → 11.3 → 11.4 → 11.5 → 11.6 only. No LTR, MMR, personalization, or learned diversification in this pipeline.

## API boundary (Phase 13)

Phase 13 will expose HTTP handlers that call `RecommendationPipeline.recommend`. Phase 11.8 does not add FastAPI routes.

## Non-goals

- FastAPI / HTTP serving
- Merging with search retrieval pipeline
- Hyperparameter tuning or evaluation-driven weight changes
- Behavioral / popularity fallbacks
- New similarity or ranking equations inside orchestration
