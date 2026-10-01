# Phase 13.3 — Search API Serving

**Status:** Search HTTP endpoint wired to production retrieval pipeline  
**Builds on:** Phase 13.1 contracts, Phase 13.2 FastAPI foundation  
**Defers:** Automated lifespan loading of BM25/embeddings/PostgreSQL in default `create_app()`

## Endpoint

| Method | Route | Handler |
|--------|-------|---------|
| POST | `/api/v1/search` | `SearchServingService.search()` |

Request body: `SearchApiRequest` (`query`, `top_k`, optional `filters`).  
Response: `SearchApiResponse` (`query`, `top_k`, `results`, `request_id`, `returned_count`).

## Request / response flow

```text
POST /api/v1/search
    ↓
FastAPI validates SearchApiRequest (Pydantic)
    ↓
RequestIdDep + SearchServiceDep
    ↓
ProductionSearchServingService.search()
    ↓
build_query_representation (Phase 8 query contract)
    ↓
RetrievalRequest(top_k=request.top_k)
    ↓
ProductionRetrievalPipeline.retrieve_ranked()
    ├── RRF hybrid retriever (candidate pool)
    ├── CatalogCandidateFilter (hard constraints)
    └── Baseline ranking stage (production default)
    ↓
ranked_search_to_api_response()
    ↓
SearchApiResponse JSON
```

## Serving boundary

| Layer | Module | Role |
|-------|--------|------|
| Contracts | `productiq.serving.search_schema` | Public request/response |
| Service | `productiq.serving.search_service.ProductionSearchServingService` | Orchestration only |
| Mapping | `productiq.serving.mappers.ranked_search_to_api_response` | Strip internal scores |
| HTTP | `productiq.api.routes.search` | Thin POST handler |
| Wiring | `productiq.api.services.search_wiring` | Pipeline → service adapter |

## Existing ProductIQ components reused

1. **Query contract (Phase 8):** `build_query_representation`, `QueryRepresentation`, `QueryFilterConstraints` (`productiq.representation.query_contract`)
2. **Retrieval (Phase 4.19):** `ProductionRetrievalPipeline.retrieve_ranked`, `RetrievalRequest` (`productiq.retrieval.production_pipeline`, `productiq.retrieval.contracts`)
3. **RRF + filtering:** Existing pipeline internals (`rrf_retriever`, `CatalogCandidateFilter`, `constraints_are_active`)
4. **Ranking (Phase 10.5):** Baseline path via `run_baseline_ranking_stage` / `ProductionRankingStageConfig` inside the pipeline (not LTR)
5. **Ranked domain result:** `RankedSearchResponse` (`productiq.retrieval.ranked_search`)
6. **Production factory (deployment):** `create_production_retrieval_pipeline_from_retrievers` (`productiq.retrieval.production_factory`) — used by deploy/integration, not imported by routes

There is no separate “query understanding” NLP module in the repository; normalization and constraint attachment are performed by `build_query_representation`, which is the Phase 8 query-side contract entry point.

## Dependency injection

- `create_app(search_service=...)` sets `app.state.search_service`.
- Routes use `SearchServiceDep` → `get_search_service()`; unset service → `ConfigurationError` (503).
- Production deployments construct `ProductionSearchServingService(pipeline)` at startup (see integration smoke) and pass it to `create_app`.
- Tests use fakes, `dependency_overrides`, or in-memory pipelines from retrieval unit tests.

## Error handling

Uses Phase 13.2 handlers and `productiq.serving.errors`:

- Invalid JSON / Pydantic body → `INVALID_REQUEST` (400)
- `QueryRepresentationError`, `ValueError` on constraints → `INVALID_REQUEST`
- `RetrievalError` / `RankingError` from pipeline → `INTERNAL_ERROR` (500) — pipeline contract failures, not client typos
- `ConfigurationError` when search service not wired → `CONFIGURATION_ERROR` (503)
- Unexpected exceptions → generic `INTERNAL_ERROR` message

## Top-k semantics

- `SearchApiRequest.top_k` must be `> 0` and `≤ DEFAULT_API_MAX_TOP_K` (100, aligned with `ServingConfig.api_max_top_k` default).
- Passed as `RetrievalRequest.top_k` — final ranked list size returned to clients.
- Internal RRF pool uses `ProductionRetrievalConfig.candidate_pool_top_k` (unchanged; not exposed as API `top_k`).

## Empty results

Zero hits after hard filtering (e.g. impossible `brand_normalized`) returns HTTP 200 with `returned_count=0` and `results=[]`. Not an error.

## Deterministic behavior

Same `SearchApiRequest` against the same pipeline state yields the same ordering (inherits retrieval/ranking determinism).

## Public vs internal fields

API results expose only `product_id` and `rank`. BM25, vector, RRF, feature values, and LTR scores remain inside domain objects and are not mapped to JSON.

## Lifecycle / resource loading

Default `create_app()` does **not** load BM25 indexes, embedding models, or PostgreSQL sessions. Callers that need live search must build a `ProductionRetrievalPipeline` (e.g. via `production_factory`) during deployment startup and inject `search_service`.

## Current limitations

- `SearchApiRequest` top-k cap uses module constant `DEFAULT_API_MAX_TOP_K`; env override via `ServingConfig.api_max_top_k` is not yet bound into the Pydantic validator.
- Readiness endpoint does not yet verify search dependencies.
- No rate limiting or auth on `/search`.

## Related

- Phase 13.2: `docs/architecture/api-fastapi-foundation.md`
- Notebook: `notebooks/data_engineering/68_api_search_serving.ipynb`
