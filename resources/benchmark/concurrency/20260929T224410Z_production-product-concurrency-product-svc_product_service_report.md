# Concurrency sweep report

- **Sweep run ID:** `production-product-concurrency-product-svc`
- **Recorded (UTC):** 2026-09-29T22:44:10.549796+00:00
- **Endpoint:** product
- **Boundary:** service
- **Workload:** `product_serving_existing_v1`
- **Warmups / iterations:** 2 / 5 (independent per concurrency level)
- **Concurrency levels:** 1, 2, 4, 8
- **Runner version:** 1.0.0

## Measurements

| Concurrency | P50 ms | P95 ms | P99 ms | Throughput rps | Errors |
|-------------|--------|--------|--------|----------------|--------|
| 1 | 0.00 | 0.00 | 0.00 | 247525.007 | 0/5 |
| 2 | 0.01 | 0.03 | 0.03 | 3386.157 | 0/5 |
| 4 | 0.01 | 0.02 | 0.02 | 5462.690 | 0/5 |
| 8 | 0.01 | 0.01 | 0.01 | 6173.602 | 0/5 |

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
