# Phase 10.5 — Ranking Pipeline Integration

**Status:** Implemented  
**Scope:** Wire baseline ranking after production retrieval and hard filtering (no LTR, no HTTP layer)

## Previous architecture (Phase 4.19)

```text
QueryRepresentation
  → ProductionRetrievalPipeline.retrieve
  → RRF @ candidate_pool_top_k
  → hard filter (CatalogCandidateFilter)
  → trim to request.top_k (RRF order)
  → RetrievalResponse
```

RRF order was the final user-visible ordering.

## New architecture (Phase 10.5)

```text
QueryRepresentation
  → ProductionRetrievalPipeline.retrieve_ranked
  → RRF @ candidate_pool_top_k          (unchanged)
  → hard filter                         (unchanged)
  → RankingCandidate[] via adapters
  → extract_features_for_request        (10.2)
  → normalize_features_for_query        (10.3)
  → rank_candidates                     (10.4)
  → trim to request.top_k
  → RankedSearchResponse
```

`retrieve()` is **unchanged** for backward compatibility (RRF order, no ranking stage).

## API decision

| Method | Purpose |
|--------|---------|
| `retrieve()` | Legacy/production retrieval path; returns `RetrievalResponse` in fused order |
| `retrieve_ranked()` | Integrated search path; returns `RankedSearchResponse` with baseline ranking |

Ranking is **opt-in** via `retrieve_ranked()` plus injected `RankingProductContextProvider` and `ProductionRankingStageConfig`. Existing callers of `retrieve()` require no changes.

## Candidate pool vs final top-k

| Setting | Role |
|---------|------|
| `ProductionRetrievalConfig.candidate_pool_top_k` | RRF depth before filtering |
| `RetrievalRequest.top_k` | Final ranked results returned |

Ranking runs on **all** candidates that survive hard filtering, then `apply_ranking_top_k` applies final top-k. Example: pool 50 → filter → 18 remain → rank 18 → return 10.

## RRF role

RRF still **generates and orders the candidate pool**. Baseline ranking re-orders the filtered pool only. RRF code and contracts are not modified.

## Hard filtering

Structured constraints run **before** feature extraction and ranking. The ranker never sees filtered-out IDs. Constraints are not converted to soft weights.

## Product context

`RankingProductContextProvider` loads `RankingProductContext` (product + optional filtering metadata) for candidate IDs:

- `InMemoryRankingProductContextProvider` — tests
- `PostgresRankingProductContextProvider` — production batch lookup (same catalog rows as filtering)

No database access inside baseline ranker, normalization, or feature modules.

## Configuration

`ProductionRankingStageConfig`:

- `enabled: bool` — when `false`, `retrieve_ranked` uses retrieval-order passthrough (`10.5.0-retrieval-order`)
- `baseline_config: BaselineRankingConfig` — reuses 10.4 weights (not duplicated)

Inject via `ProductionRetrievalPipeline(..., product_context_provider=..., ranking_stage=...)`.

## Failure behavior

| Condition | Behavior |
|-----------|----------|
| Empty intent / zero fused / all filtered | Empty ranking; no feature work |
| Missing product context | `RankingError` |
| Feature / normalization / ranker errors | Propagate (`RankingError`, validation errors) |
| Ranking enabled without provider | `RankingError` |

## Response semantics

- `RetrievalResponse` — retrieval candidates (unchanged contract)
- `RankingResponse` — ranked output (10.1)
- `RankedSearchResponse` — bundles `ranking` + `retrieval_metadata` + integration counters/timings

`RankedSearchResponse.to_retrieval_response()` projects ranked top-k into retrieval candidate order for callers that still consume `RetrievalResponse`.

## Version metadata

Preserved on ranked path when baseline runs:

- `ranking.config.ranking_version` → baseline `10.4.0`
- `RankedSearchResponse.feature_schema_version` → `10.2.0`
- `RankedSearchResponse.normalization_schema_version` → `10.3.0`
- `RankedSearchResponse.ranking_pipeline_version` → `10.5.0`

## Observability (minimal)

`RankedSearchResponse` includes:

- `candidate_count_before_filter` (fused pool size when known)
- `candidate_count_after_filter`
- `candidate_count_entering_ranking`
- `timings_ms` — retrieval / feature extraction / normalization / ranking / total (smoke only)

## Code map

| Module | Role |
|--------|------|
| `production_pipeline.py` | `retrieve_ranked`, shared filter pool |
| `ranking_integration.py` | Stage orchestration |
| `ranked_search.py` | Integration response contract |
| `production_ranking_config.py` | Stage config |
| `ranking/product_context_provider.py` | Context loading |

## Non-goals

Ranking evaluation, weight tuning, LTR, Redis cache, FastAPI/frontend, deployment, Phase 10.6+.

## Notebook

`notebooks/data_engineering/42_ranking_pipeline_integration.ipynb`
