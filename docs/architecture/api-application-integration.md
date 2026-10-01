# Phase 13.6 — API Application Integration

**Status:** Single composition root for search, recommendation, and product HTTP services  
**Builds on:** Phases 13.1–13.5 individual route wiring  
**Defers:** PostgreSQL/Redis production stacks, external dependency health probes

## Application composition root

| Component | Role |
|-----------|------|
| `build_application_services()` | `productiq.api.services.application_wiring` |
| `ApplicationServices` | Frozen bundle: `ServingConfig` + optional three services |
| `create_app(application_services=...)` | Applies services to `app.state` once |

Service-specific factories remain:

- `search_wiring.py`
- `recommendation_wiring.py`
- `product_wiring.py`

The composition root **orchestrates** those helpers; it does not reimplement pipeline logic.

## Service ownership

| Resource | Owner |
|----------|--------|
| FastAPI app | `create_app()` |
| `ApplicationServices` | Built at app construction (or injected for tests) |
| Search / recommendation / product services | Long-lived instances on `app.state` |
| Pipelines / catalog index | Owned by service objects (constructed before or during `build_application_services`) |
| Request ID | Middleware + `request.state` |
| Configuration | Single `ServingConfig` on `ApplicationServices` |

No per-request service or pipeline construction in routes.

## Dependency graph

```text
create_app
  → ApplicationServices
  → app.state.search_service / recommendation_service / product_service
  → FastAPI Depends providers
  → Production*ServingService
  → domain pipelines / ProductCatalogReadProvider
```

Routes never import retrieval, recommendation, or Parquet modules directly.

## Lifecycle

1. **Startup:** `build_lifespan` sets `is_running`, logs configured service names  
2. **Requests:** reuse `app.state` service instances  
3. **Shutdown:** log shutdown (no heavy teardown in 13.6)

Heavy resources load when building services (e.g. Parquet index at provider init), not on each HTTP call.

## Configuration flow

- `ServingConfig`: `PRODUCTIQ_API_VERSION`, `PRODUCTIQ_API_MAX_TOP_K`, `PRODUCTIQ_SERVICE_NAME`
- Search/recommendation `top_k` validation uses `resolve_api_max_top_k()` → `ServingConfig().api_max_top_k` (env-aligned)

## Readiness semantics

`ComposedHealthServingService`:

- **Liveness** (`/health`): unchanged cheap check  
- **Readiness** (`/ready`): one check per service boundary (`search_serving`, `recommendation_serving`, `product_serving`)  
  - `configured` → check status `ready`  
  - `not configured` → check status `not_ready`  
  - Overall status `ready` only when **all three** are configured  

This reflects **configuration**, not PostgreSQL/BM25/model health. Real dependency probes remain deferred.

## Cross-service isolation

Unconfigured services return **503 CONFIGURATION_ERROR** on their routes only; other wired services keep working.

## Resource reuse

Same service object identity across requests (`app.state`). Parquet catalog provider reads file once at construction.

## Production wiring

Pass pre-built pipelines/catalog into `build_application_services(...)`, or inject fully built services. No mandatory PostgreSQL in 13.6.

Opt-in smoke: `PRODUCTIQ_APPLICATION_COMPOSITION_SMOKE=1` (in-memory integrated app).

## Limitations / deferred

- No automatic loading of production PostgreSQL retrieval/recommendation stacks in `create_app()`  
- Readiness does not probe BM25, embeddings, or database connectivity  
- No Redis caching layer  

## Related

- Notebook: `notebooks/data_engineering/71_api_application_integration.ipynb`
