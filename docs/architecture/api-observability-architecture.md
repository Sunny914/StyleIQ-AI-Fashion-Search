# Phase 13.9.1 — API observability contract & architecture

**Status:** Contract (13.9.1) + runtime instrumentation (13.9-B) + hardening audit (13.9-C) complete. No Prometheus, Grafana, OpenTelemetry, or SaaS integrations yet  
**Scope:** Make ProductIQ observable in production without changing serving semantics

## Goals

Phase 13.9 is **not** a performance optimization phase. It establishes vendor-neutral
contracts for:

1. **Structured logs** (event schema)
2. **Metrics** (names + bounded labels)
3. **Traces/spans** (logical span records)

**Contract** is defined in `src/productiq/observability/`. **Runtime emission** lives in
`src/productiq/observability/runtime/`. Exporters (Prometheus, OTel SDK) remain deferred.

Phase 13.8 serving benchmarks currently record empty `stage_measurements`; runtime
observability will eventually align with domain stages without reusing benchmark
harness code in production paths.

## Three signals

| Signal | Contract module | Backend (deferred) |
|--------|-----------------|-------------------|
| Logs / events | `events.py` | Structured log pipeline |
| Metrics | `metrics.py` | Prometheus / statsd / cloud |
| Traces | `tracing.py` | OpenTelemetry / vendor APM |

## Layer ownership

| Layer | Owns |
|-------|------|
| **API** | HTTP method, route, request ID, HTTP status, HTTP latency |
| **Serving** | Service operation, domain outcome, domain latency, result counts, domain error classification |
| **Domain pipelines** | Retrieval, ranking, recommendation generation stages, candidate counts, stage timing |

API code must **not** depend on internal ML implementation details. Domain stages emit
events/spans through contracts, not ad hoc strings.

## Request context

Existing mechanism (unchanged in 13.9.1):

- Header: `X-Request-ID`
- Middleware: `productiq.api.middleware.request_id.RequestIdMiddleware`
- Contextvar: `productiq.api.context.get_request_id()`

Observability context (`ObservabilityContext`) adds:

- `request_id` (from API contextvar when not overridden)
- `service_name` (default `productiq`)
- `operation`
- optional bounded `correlation_id` (secondary; not a second request-ID system)

Builder: `build_observability_context()`.

## Event naming

Registered names (`ObservabilityEventName`):

- `api.request.started` / `completed` / `failed`
- `search.request.completed`
- `recommendation.request.completed`
- `product.request.completed`
- `retrieval.completed`
- `ranking.completed`
- `recommendation.generation.completed`

Ad hoc event strings are disallowed at the contract boundary (`assert_registered_event_name`).

## Event schema

`ObservabilityEvent` (frozen Pydantic):

- `timestamp_utc`, `event_name`, `request_id`, `service_name`, `operation`
- `outcome`, `duration_ms`, `error_code` (API taxonomy)
- bounded `metadata` (allowlist + prohibited keys)

Contract version: `OBSERVABILITY_CONTRACT_VERSION` (`1.0.0`).

## Metrics contract

Stable names (`MetricName`), examples:

- `productiq_api_requests_total`
- `productiq_api_request_duration_ms`
- `productiq_api_errors_total`
- `productiq_search_requests_total` / `productiq_search_duration_ms`
- `productiq_recommendation_requests_total` / `productiq_recommendation_duration_ms`
- `productiq_product_requests_total` / `productiq_product_duration_ms`

Observations: `MetricObservation` (in-process contract only).

## Metric dimensions (bounded)

Allowed label keys are defined per metric in `METRIC_ALLOWED_LABELS`.

**Forbidden** high-cardinality labels (never use as metric labels):

- `request_id`, `product_id`, `seed_product_id`, `query`, `user_id`, `session_id`, raw exception text, trace/span IDs

Acceptable examples: `endpoint`, `operation`, `status_class`, `outcome`, `recommendation_type`, `error_code`.

## Error taxonomy

Observability reuses `ApiErrorCode` from `productiq.serving.errors`:

`INVALID_REQUEST`, `NOT_FOUND`, `CONFIGURATION_ERROR`, `SERVICE_UNAVAILABLE`, `INTERNAL_ERROR`

No competing observability error enum.

## Security & privacy

Prohibited in event metadata (non-exhaustive): credentials, tokens, embeddings, full
queries, raw headers, stack traces, arbitrary request bodies.

Optional bounded fields when explicitly allowlisted: `query_length`, `top_k`, `filter_count`, `result_count`.

## Vendor neutrality

Domain contracts do not reference Prometheus, Grafana, OpenTelemetry, Datadog, New Relic,
or CloudWatch. Exporters and collectors belong to later sub-phases.

## Deferred integrations

- Log shipping / JSON log format adapters
- Prometheus registry & HTTP `/metrics`
- OpenTelemetry tracer provider
- Dashboards & alerting
- Wiring events/metrics into FastAPI middleware and serving services (13.9.2+)

## Tests

- `tests/observability/test_observability_contract.py` — schema, naming, context, metrics, metadata allowlist
- `tests/observability/test_observability_runtime.py` — runtime wiring, concurrency, capacity, overhead observation
- `tests/observability/test_observability_audit.py` — Phase 13.9-C hardening audit (leakage, cardinality, isolation, stages)

## Phase 13.9-C — Final audit (complete)

Final engineering block for Phase 13.9. Audit artifact:

- `resources/benchmark/observability_phase_13_9_final_audit.json`
- `resources/benchmark/observability_phase_13_9_final_audit.md`

Regenerate: `python scripts/run_observability_phase_13_9_audit.py`

| Area | Result |
|------|--------|
| Telemetry failure isolation | Best-effort `_safe_emit`; domain/API semantics unchanged |
| Security / leakage | Runtime metadata allowlist + prohibited keys; HTTP secrets not logged |
| Metric cardinality | `MetricObservation` validation; no high-cardinality labels in runtime paths |
| Stage timing | Monotonic `observe_stage`; documented span names per search/rec/product |
| Request correlation | Single `RequestIdMiddleware` → API context → observability context |
| Concurrency | Thread-safe collector; stress tests |
| Capacity | Drop-oldest per channel; `stats.dropped_*` documented |
| Production path | Unit + `create_app` composition verified; real DB/BM25 opt-in only |
| Performance | Overhead ratio test is an observation, not an SLO |

## Limitations

- No external exporters or `/metrics` endpoint yet.
- Request ID middleware behavior unchanged.
- Span records are logical stage timing only (not distributed tracing).
- Real PostgreSQL/pgvector/BM25 production telemetry path: `NOT_RUN` unless opt-in flags set.
