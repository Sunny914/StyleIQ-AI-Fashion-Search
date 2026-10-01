# Serving concurrency benchmark artifacts (Phase 13.8.6)

Controlled concurrency and throughput sweeps for search, recommendation, and
product serving boundaries.

## Experiment design

- **Concurrency levels (default):** 1, 2, 4, 8 (configurable via `ConcurrencySweepSettings`)
- **Warmups / iterations (default):** 5 warmups and 30 measured iterations **per concurrency level**
- **Workload:** fixed per endpoint (see `concurrency_workloads.py`); same logical request at every level
- **Boundaries:** API (FastAPI `TestClient`) and service (`*ServingService` methods), reported separately

## Workloads reused

| Endpoint | workload_id |
|----------|-------------|
| Search | `search_serving_lexical_v1` |
| Recommendation | `recommendation_serving_brand_activity_v1` |
| Product | `product_serving_existing_v1` |

## Throughput

`successful_requests / measured_wall_seconds` per concurrency level (13.8.2 runner semantics).

## Errors

`success_count + error_count == total_attempts` for each level. HTTP ≥400 counts as API errors.

## Prerequisites

### Product-only sweep (no PostgreSQL)

- `PRODUCTIQ_SERVING_CONCURRENCY_BENCHMARK=1`
- `resources/processed/product_catalog.parquet`

### Search / recommendation production sweeps

Additionally require integration flags and stacks from 13.8.3 / 13.8.4 (not run in default CI).

## Run (product sweep)

```bash
pytest tests/serving/test_serving_concurrency_benchmark_production.py -q
```

Or:

```bash
python scripts/run_serving_concurrency_benchmark.py
```

## Thread safety

See `thread_safety_audit.py` notes embedded in sweep artifacts. No production synchronization was added for this phase.

## Limitations

- Descriptive measurements only — no ranking of concurrency levels
- Environment-specific; not CI gates
- Search/recommendation production sweeps pending when PostgreSQL/BM25 stacks are available
