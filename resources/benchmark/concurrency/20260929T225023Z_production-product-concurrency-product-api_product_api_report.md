# Concurrency sweep report

- **Sweep run ID:** `production-product-concurrency-product-api`
- **Recorded (UTC):** 2026-09-29T22:50:23.746701+00:00
- **Endpoint:** product
- **Boundary:** api
- **Workload:** `product_serving_existing_v1`
- **Warmups / iterations:** 2 / 5 (independent per concurrency level)
- **Concurrency levels:** 1, 2, 4, 8
- **Runner version:** 1.0.0

## Measurements

| Concurrency | P50 ms | P95 ms | P99 ms | Throughput rps | Errors |
|-------------|--------|--------|--------|----------------|--------|
| 1 | 2.08 | 3.21 | 3.33 | 461.877 | 0/5 |
| 2 | 4.35 | 8.59 | 8.64 | 297.286 | 0/5 |
| 4 | 6.93 | 7.91 | 8.00 | 347.780 | 0/5 |
| 8 | 8.94 | 9.76 | 9.90 | 399.789 | 0/5 |

## Thread-safety notes

- ProcessedParquetProductCatalogReadProvider builds an immutable in-memory index at startup.
- get_product is a dict lookup; concurrent reads are expected to be safe after initialization.
- Parquet load occurs once; not included in per-request latency samples.
- FastAPI TestClient drives concurrent requests from worker threads in the 13.8.2 runner.
- Thread safety was reviewed but not proven; failures at higher concurrency are reported, not hidden.
- This phase measures behavior; it does not add locks, pools, or caches to production code.

## Limitations

- Descriptive measurements only; no configuration is ranked or recommended.
- Throughput uses successful requests divided by measured wall time per level.
- Warmups are executed independently at each concurrency level.
