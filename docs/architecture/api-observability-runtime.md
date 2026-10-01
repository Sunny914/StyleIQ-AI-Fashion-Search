# Phase 13.9-B — Runtime observability instrumentation

**Status:** In-process telemetry wired; hardened under Phase 13.9-C. No external exporters.

## Flow

```text
HTTP request
  → RequestIdMiddleware (outer; sets contextvar + X-Request-ID)
  → ObservabilityMiddleware (binds app.state.observability_sink)
  → ResilienceMiddleware (rate limit, concurrency, request timeout — Phase 13.10-B)
  → FastAPI route
  → serving service (search / recommendation / product)
  → domain pipeline stages (spans via observe_stage)
  → InMemoryObservabilityCollector (default on create_app)
```

## Sink

- Protocol: `ObservabilitySink`
- Default app sink: `InMemoryObservabilityCollector(max_entries_per_channel=5000)`
- When a channel is full, **oldest entries are dropped**; `stats.dropped_*` counters increment.
- Tests may replace `app.state.observability_sink` or bind via `bind_observability_sink()`.
- `NullObservabilitySink` for overhead baselines.

## Emission

Central module: `productiq.observability.runtime.emitter`

- `record_event` / `record_metric` / `record_span` — best-effort (exceptions swallowed)
- HTTP: `api.request.started|completed|failed` + API metrics
- Serving: `search|recommendation|product.request.completed` + domain metrics
- Domain: `retrieval.completed`, `ranking.completed`, `recommendation.generation.completed`
- Stage timing: `observe_stage()` → `ObservabilitySpan` (monotonic duration)

## Instrumentation points

| Layer | Location |
|-------|----------|
| HTTP | `api/middleware/observability.py` |
| Search | `serving/search_service.py` + pipeline timings |
| Recommendation | `recommendation/recommendation_pipeline.py` + `serving/recommendation_service.py` |
| Product | `serving/product_service.py` |

## Request ID

Same `X-Request-ID` / `productiq.api.context` as Phase 13.2. Non-HTTP callers may pass explicit IDs to serving methods; contextvar optional.

## Failure isolation

Telemetry failures never alter HTTP status or domain outcomes.

## Performance

Lightweight overhead tests in:

- `tests/observability/test_observability_runtime.py::test_instrumentation_overhead_observation`
- `tests/observability/test_observability_audit.py::test_instrumentation_overhead_repeated_observation_not_slo`

These compare wall-clock ratios with and without telemetry. **Not an SLO** — engineering observations only.

## Phase 13.9-C hardening

Audit module: `productiq.observability.phase_13_9_audit`

- Snapshot auditors for metadata leakage, metric cardinality, span timing
- Final artifacts under `resources/benchmark/observability_phase_13_9_final_audit.*`
- Full regression suite: `tests/observability/test_observability_audit.py`

## Deferred

Prometheus, OpenTelemetry, Grafana, log shipping adapters (post–Phase 13.9).
