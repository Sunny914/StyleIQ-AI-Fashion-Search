# Phase 11.1 — Recommendation Contract

**Status:** Implemented  
**Scope:** Typed recommendation inputs/outputs only (no candidate generation, no recommendation ranker)

## Problem definition

Recommendation answers: **given a seed product and a recommendation mode**, which other products should be shown? Search answers: **given a query**, which products match? The seed/context path is not interchangeable with query-driven retrieval.

## Why recommendation is distinct from search

| Concern | Search | Recommendation |
|---------|--------|------------------|
| Primary input | `QueryRepresentation` | Seed product + `RecommendationType` |
| Candidate generation | BM25, semantic, RRF | Future vector/attribute/behavioral generators |
| Filtering | Query constraints on catalog | Optional `QueryFilterConstraints` on candidates |
| Ranking | Search ranking (Phase 10) | Separate recommendation ranking (future) |
| Output | Ranked retrieval results | `RecommendationResponse` |

Recommendation is **not** a thin alias of search. `RecommendationRequest` is **not** coupled to `RetrievalRequest` or `RankingRequest`.

## Recommendation modes

Domain modes (`RecommendationType`):

- `SIMILAR`
- `ALTERNATIVE`
- `COMPLEMENTARY`
- `PERSONALIZED`

`SUPPORTED_RECOMMENDATION_TYPES` includes all enum values. **`IMPLEMENTED_RECOMMENDATION_TYPES` is empty in Phase 11.1** — contracts only; no strategy is wired.

## Current scope vs future scope

| Phase 11.1 | Later phases |
|------------|--------------|
| Contracts, config, invariants, tests, docs | Candidate generation (vector, BM25, attribute, …) |
| Seed exclusion, determinism rules | Recommendation features & ranker |
| Filter facet reuse via `QueryFilterConstraints` | Personalization, diversity, evaluation, API |

## Architecture

```text
Seed / context
  → candidate generation (future)
  → recommendation filtering (future)
  → recommendation features (future)
  → recommendation ranking (future)
  → diversity / constraints (future)
  → RecommendationResponse
```

Search path remains:

```text
Query → retrieval → filtering → search ranking → search results
```

## Request contract — `RecommendationRequest`

- `seed_product_id` — non-empty stable identity
- `recommendation_type` — `RecommendationType`
- `top_k` — positive, `top_k <= config.max_top_k` (default max **100**)
- `filters` — optional `QueryFilterConstraints` (same facet language as search hard filters)
- `config` — `RecommendationConfig`

Represents **intent**, not retrieval mechanics.

## Candidate contract — `RecommendationCandidate`

- `product_id`
- `candidate_generation_score` — optional, finite; **not** the final recommendation score
- `source` — `RecommendationCandidateSource` (`VECTOR`, `ATTRIBUTE`, `BM25`, `POPULARITY`, `BEHAVIORAL`)

Generators are **not** implemented in 11.1.

## Ranked recommendation — `RankedRecommendation`

- `product_id`, `rank` (1-based contiguous in responses), `recommendation_score` (finite)
- Optional embedded `RecommendationCandidate` for provenance (identity must align)

## Response contract — `RecommendationResponse`

- `seed_product_id`, `recommendation_type`
- `recommendations` — ordered by ascending `rank`
- `requested_top_k`, `returned_recommendation_count` (computed)
- `config`

Validation includes: unique product IDs, contiguous ranks, `returned_recommendation_count <= requested_top_k`, **seed product never appears in recommendations**.

## Configuration / versioning

`RecommendationConfig.recommendation_contract_version` defaults to **`11.1.0`**.

No ranking weights, embedding parameters, or candidate-generation knobs in 11.1.

## Invariants

See `recommendation/invariants.py`:

- Unique recommendation product IDs
- Contiguous ranks, no duplicate ranks
- Finite scores
- Seed exclusion
- `top_k` / output limit helpers
- `validate_recommendation_response_invariants` — score ordering (descending by rank) and tie-break by ascending `product_id`
- `validate_recommendation_type_implemented` — fails for all modes until a later phase registers implementations

`RecommendationError` extends the existing validation exception hierarchy.

## Determinism

Identical inputs and configuration must yield identical ordering. Tie-break: `deterministic_recommendation_sort_key` → `(-recommendation_score, product_id)` (aligned with Phase 10 ranking).

## Seed-product exclusion

If `seed_product_id = "P123"`, no `RankedRecommendation.product_id` may equal `"P123"`. Enforced on `RecommendationResponse` and `validate_seed_product_excluded`.

## Domain boundaries

Recommendation contracts do not import PostgreSQL, pgvector, BM25 indexes, or the production retrieval pipeline. Phase 10 ranking primitives may be reused **later** by a recommendation ranker; they are not substituted for recommendation contracts.

## Adapters

`recommendation/adapters.py` is intentionally minimal in 11.1. Mapping from future candidate generators into contracts will live here without coupling to infrastructure.

## Future candidate-generation architecture

Multiple `RecommendationCandidateSource` values will feed a unified candidate pool per `RecommendationType`, then optional filtering, features, and ranking.

## Future ranking / personalization

Recommendation ranking and personalization are separate from search `RankingRequest` / LTR artifacts.

## Phase 11.1 limitations

- No candidate generation, retrieval, recommendation ranker, collaborative filtering, personalization, diversity, API, cache, or evaluation
- No implemented recommendation modes (`IMPLEMENTED_RECOMMENDATION_TYPES` is empty)
- Contracts and invariants only

## Code map

| Module | Role |
|--------|------|
| `recommendation/contracts.py` | Core models |
| `recommendation/config.py` | `RecommendationConfig` |
| `recommendation/invariants.py` | Invariants, determinism |
| `recommendation/adapters.py` | Placeholder for future adapters |
| `exceptions.RecommendationError` | Invariant violations |

## Notebook

`notebooks/data_engineering/47_recommendation_contract.ipynb`
