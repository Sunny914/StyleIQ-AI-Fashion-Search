# Phase 13.4 — Recommendation API Serving

**Status:** Recommendation HTTP endpoint wired to Phase 11 `RecommendationPipeline`  
**Builds on:** Phase 13.1 contracts, Phase 13.2 FastAPI foundation, Phase 13.3 search pattern  
**Defers:** Default `create_app()` loading of PostgreSQL/embeddings for recommendations

## Endpoint

| Method | Route | Handler |
|--------|-------|---------|
| POST | `/api/v1/recommendations` | `RecommendationServingService.recommend()` |

Body: `RecommendationApiRequest` (`seed_product_id`, `top_k`, optional `filters`, `recommendation_type` default `SIMILAR`).  
Response: `RecommendationApiResponse`.

## Request flow

```text
POST /api/v1/recommendations
    ↓
RecommendationApiRequest validation (SIMILAR-only at API boundary)
    ↓
RecommendationServiceDep + RequestIdDep
    ↓
ProductionRecommendationServingService.recommend()
    ↓
RecommendationRequest (domain)
    ↓
RecommendationPipeline.recommend()
    ├── seed resolution (RecommendationCatalogAccess)
    ├── candidate generation (vector / attribute / BM25 generators)
    ├── content similarity (ContentSimilarityEngine)
    ├── feature extraction + baseline ranker
    └── selection / diversity / hard constraints
    ↓
recommendation_response_to_api()
    ↓
JSON
```

## Serving boundary

| Layer | Module |
|-------|--------|
| Contracts | `productiq.serving.recommendation_schema` |
| Service | `productiq.serving.recommendation_service.ProductionRecommendationServingService` |
| Mapping | `productiq.serving.mappers.recommendation_response_to_api` |
| HTTP | `productiq.api.routes.recommendations` |
| Wiring | `productiq.api.services.recommendation_wiring` |

## Phase 11 components reused

- `RecommendationRequest`, `RecommendationResponse`, `RecommendationType` — `productiq.recommendation.contracts`
- `RecommendationPipeline.recommend()` — `productiq.recommendation.recommendation_pipeline`
- `RecommendationConfig` / pool semantics — `productiq.recommendation.config`
- Seed catalog — `RecommendationCatalogAccess` / `InMemoryRecommendationCatalog` / `PostgresRecommendationCatalog` — `productiq.recommendation.seed_product`
- Generators — `productiq.recommendation.generators.*`
- Similarity — `ContentSimilarityEngine`
- Ranking — `BaselineRecommendationRanker` / `rank_recommendations`
- Selection — `select_recommendations_for_request`, `RecommendationSelectionConfig`
- Production guardrails — `assert_production_recommendation_request`, pipeline invariants

No recommendation logic was duplicated in the API or serving layers.

## SIMILAR-only production support

`RecommendationApiRequest` rejects non-`SIMILAR` types at validation (`ValueError` → 400). The domain pipeline also enforces `IMPLEMENTED_RECOMMENDATION_TYPES` via `validate_recommendation_type_implemented` — no silent fallback to SIMILAR.

## Seed-product semantics

Missing seed rows raise `CatalogValidationError` with message prefix `catalog row missing for seed product_id`. HTTP layer maps that pattern to **404** `NOT_FOUND` with message **Seed product not found** (no product id echoed). Other `CatalogValidationError` cases remain **503** `SERVICE_UNAVAILABLE`.

## Shortfall and empty results

- Zero candidates → **200**, empty `recommendations`, `returned_count=0`
- Selection constraints (e.g. `max_per_brand`) may return fewer than `top_k` — **200**, no constraint relaxation, no filler products

## Constraint behavior

Optional API `filters` (`QueryFilterConstraints`) pass through to `RecommendationRequest.filters` and into selection context — same hard-filter semantics as Phase 11.

## Top-k semantics

- API validates `top_k` ≤ `DEFAULT_API_MAX_TOP_K` (100)
- Domain `RecommendationRequest.top_k` is final response cap
- Internal `candidate_pool_top_k` on `RecommendationConfig` remains separate (default 50)

## Error mapping

| Situation | HTTP | Code |
|-----------|------|------|
| Invalid body / unsupported type / bad top_k | 400 | `INVALID_REQUEST` |
| Missing seed product | 404 | `NOT_FOUND` |
| Unconfigured `recommendation_service` | 503 | `CONFIGURATION_ERROR` |
| `RecommendationError` (pipeline) | 500 | `INTERNAL_ERROR` |
| Other catalog/DB validation | 503 | `SERVICE_UNAVAILABLE` |
| Unexpected | 500 | `INTERNAL_ERROR` |

Centralized in `productiq.api.error_mapping` + Phase 13.2 exception handlers.

## Dependency injection

`create_app(recommendation_service=...)` sets `app.state.recommendation_service`. Routes use `RecommendationServiceDep`. Unset → explicit 503.

## Lifecycle / resources

Default app factory does not construct `RecommendationPipeline`. Production injects a pipeline built at startup (PostgreSQL catalog, embeddings, generators as in Phase 11 tests/integration).

## Public vs internal fields

API items expose `product_id`, `rank`, and `recommendation_score` (per Phase 13.1 contract). Internal candidate generation scores, similarity components, feature vectors, and generator provenance are not exposed.

## Limitations

- No live PostgreSQL recommendation smoke in default CI (optional `PRODUCTIQ_RECOMMENDATION_API_SMOKE=1` runs in-memory pipeline through HTTP)
- Readiness does not probe recommendation dependencies
- `RecommendationConfig` is not tunable via HTTP (domain defaults apply)

## Related

- Notebook: `notebooks/data_engineering/69_api_recommendation_serving.ipynb`
- Phase 13.3 search: `docs/architecture/api-search-serving.md`
