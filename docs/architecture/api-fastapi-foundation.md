# Phase 13.2 — FastAPI Application Foundation

**Status:** HTTP adapter implemented (health/readiness; domain routes deferred)  
**Builds on:** Phase 13.1 serving contracts (`src/productiq/serving/`)  
**Defers to Phase 13.3+:** Search/recommendation/product routes, real readiness probes, pipeline wiring

## Purpose

Phase **13.2** adds a production-shaped **FastAPI application** without moving retrieval, ranking, recommendation, or evaluation logic into HTTP handlers.

```text
HTTP client
    ↓
FastAPI (src/productiq/api/)
    ↓
Middleware (request ID)
    ↓
Router (thin)
    ↓
Dependency injection
    ↓
Serving service protocol (Phase 13.1)
    ↓
Existing ProductIQ pipelines (later phases)
```

**FastAPI is the framework adapter.** Public contracts remain in `productiq.serving`.

## Application factory

Entry point: `productiq.api.create_app()` → `FastAPI`.

The factory:

1. Accepts optional `ServingConfig` and `HealthServingService`
2. Configures OpenAPI metadata and `/api/v1` documentation URLs
3. Registers request ID middleware and exception handlers
4. Mounts the v1 router under `SERVING_API_ROUTE_PREFIX` (`/api/v1`)
5. Uses a **lifespan** hook for startup/shutdown logging only (no BM25, embeddings, or DB pools at import)

No global singleton app instance is required; tests construct isolated apps.

## Router architecture

| Module | Responsibility |
|--------|----------------|
| `api/routes/v1_router.py` | Aggregates v1 routes |
| `api/routes/health.py` | `GET /health`, `GET /ready` |

Full paths (from `productiq.serving.versioning`):

- `GET /api/v1/health`
- `GET /api/v1/ready`

Search, recommendations, and product routes are **not** registered in 13.2 (no fabricated responses).

## Dependency injection

`api/dependencies.py` exposes FastAPI `Depends` providers:

- `get_serving_config`, `get_health_service`, `get_request_id`
- `get_search_service`, `get_recommendation_service`, `get_product_service` — raise `ConfigurationError` when `app.state.*_service` is unset

**Production:** set real services on `app.state` during lifespan or factory extension.  
**Tests:** `app.dependency_overrides[...]` or inject fakes via `create_app(health_service=...)`.

## Request ID lifecycle

`RequestIdMiddleware`:

- Reads optional `X-Request-ID`
- Validates length (≤128) and character set `[A-Za-z0-9._-]`
- Generates a UUID when missing or unsafe
- Sets `request.state.request_id` and a context variable (`api/context.py`)
- Echoes `X-Request-ID` on the response

No authentication or distributed tracing in this phase.

## Exception handling

Handlers in `api/exception_handlers.py`:

| Source | API code | Notes |
|--------|----------|--------|
| Pydantic / FastAPI validation | `INVALID_REQUEST` | Generic client message |
| `ApiNotFoundError` | `NOT_FOUND` | HTTP-layer not found |
| Other `ProductIQError` | Via `map_exception_to_api_error` / `map_http_exception_to_api_error` | No tracebacks or secrets |
| Unexpected `Exception` | `INTERNAL_ERROR` | Fixed safe message |

Domain mapping (`serving/errors.py`):

- **Client/input:** `ValueError`, `QueryRepresentationError`, generic `ValidationError`
- **Pipeline failures:** `RetrievalError`, `RankingError`, `RecommendationError` → `INTERNAL_ERROR` (not `INVALID_REQUEST`)
- **Configuration:** `ConfigurationError` → `CONFIGURATION_ERROR`
- **Infrastructure:** `DatabaseError`, catalog errors → `SERVICE_UNAVAILABLE`

## HTTP status mapping

Central map: `api/http_status.py` (`HTTP_STATUS_BY_API_ERROR`).

| `ApiErrorCode` | HTTP status |
|----------------|-------------|
| `INVALID_REQUEST` | 400 |
| `NOT_FOUND` | 404 |
| `CONFIGURATION_ERROR` | 503 |
| `SERVICE_UNAVAILABLE` | 503 |
| `INTERNAL_ERROR` | 500 |

Configuration and dependency outages use 5xx, not 400.

## Health and readiness

- **Health:** `DefaultHealthServingService.health()` — static liveness, no I/O
- **Readiness:** `DefaultHealthServingService.ready()` — returns `ready` with empty `checks` until Phase 13.3+ probes (PostgreSQL, pgvector, indexes, models)

## Lifespan

`api/lifespan.py` — `build_lifespan` sets `app.state.is_running` and logs start/stop. Resource loading belongs in later integration phases.

## OpenAPI

- Title: ProductIQ API
- Version: `ServingConfig.api_version` (default `v1`)
- Schema UI: `/api/v1/docs`, `/api/v1/redoc`, `/api/v1/openapi.json`

## Testing architecture

`tests/api/test_fastapi_app.py` uses `TestClient` with:

- Factory and route smoke tests
- Request ID behavior
- Error handlers (validation, domain, not found, configuration, unexpected)
- Dependency overrides
- Lifespan flag
- No PostgreSQL, BM25, or model downloads

## Phase 13.3+ (deferred)

- Wire `SearchServingService`, `RecommendationServingService`, `ProductServingService` to production pipelines
- Real readiness checks per dependency
- Optional host/process entrypoint (uvicorn) with deployment config
- Rate limiting, auth, and observability exports (out of scope for 13.2)

## Related artifacts

- Phase 13.1: `docs/architecture/api-serving-architecture.md`, notebook `66_api_serving_contract.ipynb`
- Phase 13.2 notebook: `67_api_fastapi_foundation.ipynb`
