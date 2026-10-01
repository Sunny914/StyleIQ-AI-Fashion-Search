# Phase 13 — Production serving (final)

**Phase 13 status:** Complete (architecture implemented and locally validated).

## Request lifecycle

```text
HTTP
  → RequestIdMiddleware          (outer; X-Request-ID / contextvar)
  → ObservabilityMiddleware      (events, metrics, spans — best-effort)
  → ResilienceMiddleware         (body size, rate limit, concurrency, optional timeout)
  → FastAPI route
  → Serving service              (search / recommendation / product)
  → Domain pipeline              (retrieval, ranking, recommendation, catalog)
```

Successful responses and controlled errors preserve existing API contracts. Domain algorithms are unchanged from Phase 12 and earlier.

## Production safety guarantees (local validation)

| Area | Guarantee |
|------|-----------|
| Configuration | Validated `ServingConfig`; public fields exclude secrets |
| Health | `/health` = process liveness only |
| Readiness | `/ready` = configured workloads + explicit `not_checked` external probes |
| Errors | Stable `ApiErrorCode` → HTTP mapping; sanitized client messages |
| Rate limiting | Optional fixed-window limiter; 429 + `Retry-After` when known |
| Concurrency | Optional per-endpoint gates (search/recommendation) |
| Observability | Vendor-neutral in-process telemetry; failures isolated |
| Resilience keys | Hashed; raw client identifiers not logged or metric-labeled |

## Limitations (explicit)

- **Not** horizontally shared rate limits (in-memory per process).
- **Not** hard-cancel of sync CPU via HTTP timeout.
- **Not** authenticated identity for rate limiting (deployment key + client id hash).
- **Not** full PostgreSQL/pgvector/BM25 validation in default test gate (`INFRASTRUCTURE_UNAVAILABLE`).
- **Not** authentication/authorization (future work).

## Closure statement

Production-serving architecture implemented and locally validated; external production infrastructure validation remains pending.

## Related docs

- [production-serving-safety.md](production-serving-safety.md) — 13.10-A
- [production-serving-resilience.md](production-serving-resilience.md) — 13.10-B
- [api-observability-runtime.md](api-observability-runtime.md) — 13.9
- Final audit: `resources/benchmark/production_serving_phase_13_10_final_audit.json`

Regenerate audit: `python scripts/run_production_serving_phase_13_10_audit.py`
