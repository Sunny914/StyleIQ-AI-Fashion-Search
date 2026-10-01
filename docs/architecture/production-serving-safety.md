# Phase 13.10-A — Production serving safety

**Status:** Configuration safety, readiness model, lifecycle boundaries, failure isolation.

## Configuration safety

`ServingConfig` (env: `PRODUCTIQ_API_VERSION`, `PRODUCTIQ_API_MAX_TOP_K`, `PRODUCTIQ_SERVICE_NAME`):

- `api_version` must match `v<major>[.<minor>...]` (bounded length)
- `api_max_top_k` in `1..1000`
- `service_name` alphanumeric plus `._-` (max 64 chars)
- Invalid values fail at settings validation (clear error, no silent defaults beyond documented bounds)
- `ServingConfig.public_fields()` / `serving_config_public_dict()` expose only non-secret fields

Secrets (passwords, DB URLs, API keys) must not appear in health, readiness, API errors, or observability (see Phase 13.9).

## Request limit relation

Search and recommendation `top_k` are validated against `resolve_api_max_top_k()` → current `ServingConfig().api_max_top_k` (env-aware). Requests above the cap return `INVALID_REQUEST` (400).

## Health vs readiness

| Endpoint | Question | I/O |
|----------|----------|-----|
| `GET /api/v1/health` | Is the process alive? | None — returns `status: ok`, service name, api_version |
| `GET /api/v1/ready` | Can configured workloads be served? | Bounded checks only — no DB/BM25 probes on each request |

## Readiness model

Per-check statuses (`DependencyReadinessStatus`):

- **configured** — serving service wired for that domain
- **not_ready** — required serving service missing for that check name
- **not_checked** — external dependency probe not implemented (explicit, not faked healthy)
- **ready** / **unknown** — reserved for future real probes

Typical checks when search is configured:

- `search_serving` → configured
- `search_retrieval_database`, `search_vector_index`, `search_bm25_index` → not_checked

Aggregate `ready` when at least one serving service is configured and no **configured** primary check is `not_ready`. Unconfigured recommendation/product checks remain `not_ready` but do not block search-only deployments.

Implementation: `productiq.serving.production_safety.readiness.build_readiness_response`.

## Lifecycle / startup

`build_lifespan` logs configured service names only; does not load models, catalogs, BM25, or run DB queries. `app.state.is_running` is set true on startup, false on shutdown.

Avoid import-time side effects in observability and serving safety modules.

## Dependency failure isolation

Errors map through `map_exception_to_api_error` / HTTP handlers:

| Code | HTTP | Use |
|------|------|-----|
| `CONFIGURATION_ERROR` | 503 | Route used but serving service not wired |
| `SERVICE_UNAVAILABLE` | 503 | Catalog/DB/load failures (`DatabaseError`, `CatalogLoadError`, …) |
| `NOT_FOUND` | 404 | Missing product/seed |
| `INTERNAL_ERROR` | 500 | Unexpected / domain pipeline failures (sanitized message) |
| `INVALID_REQUEST` | 400 | Validation |

Client messages pass through `safe_client_message` / `_sanitize_client_text` (redacts URLs, Bearer tokens, file paths, tracebacks).

## Graceful degradation matrix (application wiring)

Derived from independent FastAPI dependencies and separate service instances:

| Failure | Search | Recommendation | Product |
|---------|--------|------------------|---------|
| Search backend down (`DatabaseError` on search) | 503 | unaffected if configured | unaffected if configured |
| Product catalog down (`CatalogLoadError` on product) | unaffected | unaffected | 503 |
| Unconfigured recommendation | 503 on rec route only | 503 config | — |

Shared resources in a single deployment may correlate failures; the table reflects separate service injection in `create_app()`.

## Security boundary

- No stack traces or raw exception reprs in JSON error envelopes
- Readiness messages are fixed short strings
- No authentication layer in 13.10-A

## Import / startup note

Localized fixes (Phase 13.10-A):

- `api/lifespan.py` imports `get_logger` only inside the lifespan context manager
- `data/export/processed.py` uses stdlib `logging` for its write path

`from productiq.api.app import create_app` succeeds without PostgreSQL or BM25 artifacts when using normal test/fake wiring. Importing `productiq.api` package root may still pull heavier modules depending on import order.

## Production smoke

Opt-in: `PRODUCTIQ_PRODUCTION_SAFETY_SMOKE=1` → `tests/api/test_production_safety.py::test_production_safety_smoke_opt_in`

Real PostgreSQL/BM25/pgvector probes: **NOT_RUN / INFRASTRUCTURE_UNAVAILABLE** (readiness uses `not_checked`).

## Resilience (Phase 13.10-B)

See [production-serving-resilience.md](production-serving-resilience.md) for rate limiting, concurrency, and timeout policy.

## Phase 13 closure (13.10-C)

See [production-serving-final.md](production-serving-final.md) and `resources/benchmark/production_serving_phase_13_10_final_audit.json`.

## Known limitations

- External dependency probes deferred (`not_checked`)
- Rate limiting, circuit breakers, auth — Phase 13.10-B+
- `RetrievalError` remains `INTERNAL_ERROR` (distinct from infrastructure `DatabaseError`)

## Tests

`tests/api/test_production_safety.py`, updated `tests/api/test_readiness.py`
