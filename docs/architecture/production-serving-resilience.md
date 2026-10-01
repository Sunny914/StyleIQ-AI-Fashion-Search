# Phase 13.10-B — Production serving resilience

**Status:** In-process rate limiting, concurrency gates, request bounds, optional request timeout.

## Rate limiting

- **Abstraction:** `RateLimiter` protocol with `allow(key) -> RateLimitDecision`
- **Implementation:** `FixedWindowRateLimiter` (thread-safe, bounded `max_keys`, evicts expired windows)
- **Disabled by default:** `PRODUCTIQ_RATE_LIMIT_ENABLED=0`; enable for production traffic protection
- **Distributed backends:** Deferred — plug a Redis-backed `RateLimiter` without changing middleware

### Algorithm

Fixed window per key: `window_id = floor(epoch / window_seconds)`. Counters reset each window. When limit exceeded, `retry_after_seconds` = seconds until next window boundary (used for `Retry-After` header).

Memory: at most `rate_limit_max_keys` entries; oldest evicted on overflow.

**Multi-instance limitation:** In-memory state is per process; horizontal scale requires a shared store.

## Rate-limit key

No authentication yet. Key = `SHA-256(deployment_key + "|" + client_id)` (hashed; never logged).

| Deployment | `PRODUCTIQ_RATE_LIMIT_TRUST_FORWARDED_FOR` | Identity source |
|------------|--------------------------------------------|-----------------|
| Direct / untrusted (default) | `false` | Direct peer only — **ignores** spoofed `X-Forwarded-For` |
| Trusted reverse proxy | `true` | First `X-Forwarded-For` hop (proxy must sanitize headers) |

Configure deployment salt: `PRODUCTIQ_RATE_LIMIT_DEPLOYMENT_KEY`.

## HTTP 429

`ApiErrorCode.RATE_LIMITED` → HTTP **429** with standard `ApiErrorEnvelope`. `Retry-After` set only when retry interval is known from the window boundary.

## Concurrency protection

Separate from rate limiting:

- `PRODUCTIQ_SEARCH_CONCURRENCY_LIMIT` (0 = disabled)
- `PRODUCTIQ_RECOMMENDATION_CONCURRENCY_LIMIT` (0 = disabled)

When exhausted: `ApiErrorCode.OVERLOADED` → HTTP **503**, generic message, no semaphore internals exposed.

## Request limits

| Limit | Config | Behavior |
|-------|--------|----------|
| `top_k` | existing `api_max_top_k` | unchanged validation |
| query length | `PRODUCTIQ_API_MAX_QUERY_LENGTH` (default 512) | `INVALID_REQUEST` |
| body size | `Content-Length` vs `PRODUCTIQ_API_MAX_BODY_BYTES` | `INVALID_REQUEST`, no silent truncate |

## Timeout

Optional `PRODUCTIQ_SERVING_REQUEST_TIMEOUT_SECONDS` wraps middleware `call_next` in `asyncio.wait_for`. On timeout → `SERVICE_UNAVAILABLE` (503). Does not cancel sync CPU work inside thread pool; bounds total request wait time only.

## Dependency failures

Existing exception mapping unchanged (`DatabaseError` → 503, etc.). No fabricated results.

## Circuit breaker

**DEFERRED** — current production wiring is primarily in-process/local; no remote dependency warrants a breaker in this phase.

## Observability

Rejections surface as normal HTTP responses; `ObservabilityMiddleware` records `api.request.completed` with `error_code` `RATE_LIMITED` / `OVERLOADED` / etc. Metrics use bounded labels (`endpoint`, `operation`, `error_code` only).

Optional helper: `emit_traffic_rejection()` for explicit resilience-layer events (not duplicated in middleware by default).

## Security

Rate-limit keys are hashed and not logged. No credentials in 429/503 envelopes.

## Tests

- `tests/api/test_resilience.py`
- `tests/serving/` — rate limiter unit tests embedded in API suite

Opt-in smoke: `PRODUCTIQ_RESILIENCE_SMOKE=1`

## Known limitations

- In-memory rate limit not shared across replicas
- Request timeout does not hard-cancel blocking domain CPU
- Product endpoint has no concurrency gate (catalog reads are lighter; add if needed later)

## Phase 13 closure

Integrated audit and matrix: [production-serving-final.md](production-serving-final.md) and `resources/benchmark/production_serving_phase_13_10_final_audit.json`.
