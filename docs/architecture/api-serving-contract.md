# Phase 13.1 — API Serving Contract

**Status:** Implemented (schemas + mapping; HTTP in Phase 13.2)  
**Package:** `productiq.serving`

## Public error envelope

Failed requests return:

```json
{
  "error": {
    "code": "INVALID_REQUEST",
    "message": "Human-readable, client-safe text",
    "request_id": "optional-correlation-id"
  }
}
```

### Error codes

| Code | Typical domain sources |
|------|-------------------------|
| `INVALID_REQUEST` | `ValidationError`, `QueryRepresentationError`, `RetrievalError`, `RankingError`, `RecommendationError`, Pydantic/`ValueError` on API models |
| `NOT_FOUND` | Reserved for unknown `product_id` (Phase 13.2) |
| `CONFIGURATION_ERROR` | `ConfigurationError` |
| `SERVICE_UNAVAILABLE` | `DatabaseError`, `CatalogLoadError`, `CatalogValidationError` |
| `INTERNAL_ERROR` | Other `ProductIQError`, unexpected exceptions |

Mapping: `map_exception_to_api_error()` in `productiq.serving.errors`. Internal stack traces and implementation details are **not** exposed.

## Versioning

- Prefix: **`/api/v1`**
- Constants: `SERVING_API_ROUTE_PREFIX`, `SERVING_API_MAJOR_VERSION`

## POST `/api/v1/search`

### Request — `SearchApiRequest`

| Field | Type | Notes |
|-------|------|-------|
| `query` | string | Min length 1; normalized in service layer (Phase 13.2) |
| `top_k` | int | `> 0`, `≤ PRODUCTIQ_API_MAX_TOP_K` (default 100) |
| `filters` | `QueryFilterConstraints` \| null | Same facet contract as search filtering |

Example:

```json
{
  "query": "black Nike running shoes",
  "top_k": 10
}
```

### Response — `SearchApiResponse`

| Field | Notes |
|-------|-------|
| `query` | Echo of normalized query |
| `top_k` | Requested cap |
| `results[]` | `product_id`, `rank` only (no BM25/vector/RRF diagnostics) |
| `request_id` | Correlation |
| `returned_count` | Len(results) |

**Domain mapping:** `ProductionRetrievalPipeline.retrieve_ranked()` → `RankedSearchResponse` → `ranked_search_to_api_response()`.

## POST `/api/v1/recommendations`

### Request — `RecommendationApiRequest`

| Field | Type | Notes |
|-------|------|-------|
| `seed_product_id` | string | Required |
| `recommendation_type` | enum | **`SIMILAR` only** in production API |
| `top_k` | int | Same cap as search |
| `filters` | `QueryFilterConstraints` \| null | Optional |

### Response — `RecommendationApiResponse`

| Field | Notes |
|-------|-------|
| `seed_product_id` | Echo |
| `recommendation_type` | Echo |
| `top_k` | Requested cap |
| `recommendations[]` | `product_id`, `rank`, `recommendation_score` |
| `request_id`, `returned_count` | Metadata |

**Domain mapping:** `RecommendationPipeline.recommend()` → `RecommendationResponse` → `recommendation_response_to_api()`.

## GET `/api/v1/products/{product_id}`

### Response — `ProductApiResponse`

API-safe catalog fields only (no parquet paths, DB URLs, or embedding columns):

- `product_id`, `brand`, `description`, `image_url`, `product_url`, `category_gender`, `product_type`
- `request_id`

**Read boundary:** infrastructure supplies `ProductCatalogReadModel`; service maps via `product_read_model_to_api()`.

## GET `/api/v1/health`

`HealthResponse`:

- `status`: `"ok"`
- `service`: e.g. `"productiq"`
- `api_version`: e.g. `"v1"`

No dependency checks.

## GET `/api/v1/ready`

`ReadinessResponse`:

- `status`: `ready` \| `not_ready`
- `checks[]`: optional named probes (`DependencyReadinessStatus`)

Phase 13.1 defines the contract only; expensive probes deferred.

## Service protocols (dependency injection)

| Protocol | Method |
|----------|--------|
| `HealthServingService` | `health()`, `ready()` |
| `SearchServingService` | `search(request, request_id=…)` |
| `RecommendationServingService` | `recommend(request, request_id=…)` |
| `ProductServingService` | `get_product(product_id, request_id=…)` |

Implementations live in Phase 13.2; tests use in-memory fakes.

## Testing boundary

| Layer | What to test |
|-------|----------------|
| `productiq.serving` | API schema validation, error mapping, mappers |
| Domain pipelines | Existing retrieval/ranking/recommendation/evaluation suites (unchanged) |
| FastAPI (13.2+) | Route + DI integration with fake services |

## Future extension points

- **Redis:** cache layer **below** services or behind catalog/read interfaces — not in routes
- **Next.js:** HTTP client to `/api/v1/*`
- **Observability:** `request_id` propagation, metrics on service boundaries
- **Auth:** middleware in FastAPI; services remain identity-agnostic
