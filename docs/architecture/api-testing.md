# Phase 13.7 — API Testing & Integration Testing

**Status:** Systematic HTTP/API test strategy on top of Phases 13.1–13.6  
**Principle:** Real FastAPI routes and dependency wiring; deterministic fakes for serving boundaries

## Test pyramid

| Layer | Location | Runs in default CI | Dependencies |
|-------|----------|-------------------|--------------|
| Serving contracts | `tests/serving/` | Yes | Pydantic models, protocols |
| HTTP route tests | `tests/api/test_*_route.py` | Yes | `create_app` + fakes or small pipelines |
| Application integration | `tests/api/test_application_*.py`, `test_readiness.py` | Yes | In-memory pipelines/catalog |
| Cross-endpoint | `tests/api/test_api_cross_endpoint.py` | Yes | Shared `integrated_client` fixture |
| Contract/error/config/HTTP boundary | `tests/api/test_api_*.py` | Yes | Fakes in `tests/api/fakes.py` |
| PostgreSQL / production retrieval | `tests/database/`, `tests/retrieval/integration/` | No | `PRODUCTIQ_RUN_INTEGRATION_TESTS` |
| Production smoke | `tests/api/test_*_integration.py`, `test_application_production_smoke.py` | No | See flags below |

Normal API tests never load the full catalog, embedding artifacts, HNSW index, or large BM25 indexes.

## Deterministic test doubles

`tests/api/fakes.py` provides `RecordingSearchService`, `RecordingRecommendationService`, and `RecordingProductService`.

Pattern:

```text
HTTP request
  → real route + exception handlers + request-ID middleware
  → FastAPI Depends(get_*_service)
  → app.state service (or dependency override)
  → recording fake OR small in-memory pipeline
```

Routes are not mocked. Production factories are not invoked in default tests.

## Dependency overrides

Tests may set `app.dependency_overrides[get_search_service]` (and siblings) to inject fakes without changing `app.state`. Both patterns exist in `tests/api/test_*_route.py` for regression coverage.

## Configuration testing

`ServingConfig` env aliases:

- `PRODUCTIQ_API_VERSION`
- `PRODUCTIQ_API_MAX_TOP_K`
- `PRODUCTIQ_SERVICE_NAME`

HTTP `top_k` validation uses `resolve_api_max_top_k()` → `ServingConfig().api_max_top_k`. Tests in `test_api_configuration.py` set env vars per test via `monkeypatch`.

## Error contract

All failure responses use `ApiErrorEnvelope` with `code`, `message`, and `request_id`. `tests/api/test_api_errors.py` and Phase 13.2 handler tests cover mapping for every `ApiErrorCode`.

## Request ID

`X-Request-ID` behavior is defined in `request_id.py`. Dedicated coverage: `test_request_id_api.py` and foundation tests in `test_fastapi_app.py`.

## Cross-endpoint invariants

- Search hit `product_id` must be readable via GET `/products/{id}` when catalog contains that id.
- Recommendation seed must not appear in recommendation results (pipeline contract); verified on integrated app.
- Coordinated fakes in `test_api_cross_endpoint.py` prove identity chaining without production artifacts.

## Application composition

Phase 13.6 tests remain authoritative for readiness, isolation, and service reuse. Phase 13.7 adds cross-cutting contract/error/config tests without duplicating isolation matrices.

## Environment flags (opt-in)

| Flag | Purpose |
|------|---------|
| `PRODUCTIQ_RUN_INTEGRATION_TESTS` | PostgreSQL-backed tests |
| `PRODUCTIQ_PRODUCTION_RETRIEVAL_SMOKE` | Live production retrieval stack |
| `PRODUCTIQ_SEARCH_API_SMOKE` | Search API over live retrieval |
| `PRODUCTIQ_RECOMMENDATION_API_SMOKE` | Recommendation API smoke |
| `PRODUCTIQ_APPLICATION_COMPOSITION_SMOKE` | Full in-memory composed app (health/ready/search/product/recommendations) |
| `PRODUCTIQ_PRODUCT_API_SMOKE` | Processed Parquet catalog product API |

Stable names are guarded by `tests/api/test_api_smoke_flags.py`.

## Production smoke boundary

Smoke tests validate wiring and a handful of HTTP calls only. They are not benchmarks, load tests, or evaluation suites.

Prerequisites for live smokes are documented on each test module’s `pytestmark` skip reason.

## Limitations / deferred

- No auth, rate limiting, or distributed tracing tests
- Readiness does not assert external dependency health
- Full production stack smoke remains opt-in and environment-dependent

## Related

- Notebook: `notebooks/data_engineering/72_api_testing.ipynb`
- Application composition: `docs/architecture/api-application-integration.md`
