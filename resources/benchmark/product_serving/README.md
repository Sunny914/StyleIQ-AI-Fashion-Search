# Product serving performance benchmark artifacts (Phase 13.8.5)

Machine-readable `ServingBenchmarkRunResult` JSON files, suite summaries, and
Markdown reports are written here by the opt-in production benchmark.

Separate from search and recommendation serving performance artifacts.

## Purpose

Measure steady-state latency for `GET /api/v1/products/{product_id}` and
`ProductionProductServingService.get_product()` against the processed catalog
index (`ProcessedParquetProductCatalogReadProvider`).

## Catalog source

- `resources/processed/product_catalog.parquet`
- Manifest checksum (when present): `resources/processed/product_catalog.manifest.json`

The Parquet index is built **once** when the provider is constructed; that
one-time load is **not** included in per-request latency samples.

## Workloads (latency baseline)

| workload_id | product_id |
|-------------|------------|
| `product_serving_existing_v1` | `460946942002` |
| `product_serving_existing_alt_v1` | `460825114005` |
| `product_serving_existing_rich_v1` | `441118465014` |

Default settings: **5 warmups**, **30 iterations**, **concurrency=1**.

## Missing product semantics

Workload `product_serving_missing_v1` uses `productiq_perf_missing_v1` (absent
from the catalog). It is **excluded** from the primary performance suite.

- API: HTTP **404** with ProductIQ `NOT_FOUND` error contract (verified in tests)
- Generic benchmark runner treats HTTP `>=400` as measurement errors — this is
  expected for that workload and is **not** an infrastructure failure

## Prerequisites

- `PRODUCTIQ_PRODUCT_SERVING_PERFORMANCE_BENCHMARK=1`
- `resources/processed/product_catalog.parquet` on disk

No PostgreSQL required.

## Run

```bash
python scripts/run_product_serving_performance_benchmark.py
```

Or:

```bash
pytest tests/serving/test_product_serving_performance_production.py -q
```

Artifacts are environment-specific; do not treat latency numbers as CI gates.

## Limitations

- No stage-level instrumentation in 13.8.5
- Absolute latency varies by host and I/O
- Concurrency study deferred to Phase 13.8.6
