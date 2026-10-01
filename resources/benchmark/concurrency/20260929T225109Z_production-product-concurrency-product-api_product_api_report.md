# Concurrency sweep report

- **Sweep run ID:** `production-product-concurrency-product-api`
- **Recorded (UTC):** 2026-09-29T22:51:09.683106+00:00
- **Endpoint:** product
- **Boundary:** api
- **Workload:** `product_serving_existing_v1`
- **Warmups / iterations:** 2 / 5 (independent per concurrency level)
- **Concurrency levels:** 1, 2, 4, 8
- **Runner version:** 1.0.0

## Measurements

| Concurrency | P50 ms | P95 ms | P99 ms | Throughput rps | Errors |
|-------------|--------|--------|--------|----------------|--------|
| 1 | 1.75 | 3.03 | 3.19 | 474.208 | 0/5 |
| 2 | 7.04 | 28.17 | 28.30 | 127.120 | 0/5 |
| 4 | 9.01 | 10.67 | 10.85 | 327.927 | 0/5 |
| 8 | 8.47 | 9.16 | 9.19 | 412.926 | 0/5 |

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
