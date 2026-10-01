# Recommendation serving performance benchmark artifacts (Phase 13.8.4)

Machine-readable `ServingBenchmarkRunResult` JSON files, suite summaries, and
Markdown reports are written here by the opt-in production benchmark.

Separate from:

- `resources/benchmark/search_serving/` (search latency)
- Phase 11/12 relevance evaluation artifacts

## Prerequisites

- `PRODUCTIQ_RUN_INTEGRATION_TESTS=1`
- `PRODUCTIQ_PRODUCTION_RETRIEVAL_SMOKE=1`
- `PRODUCTIQ_RECOMMENDATION_SERVING_PERFORMANCE_BENCHMARK=1`
- PostgreSQL with pgvector embeddings (see retrieval integration conftest)
- BM25 index and/or benchmark-scoped fallback (see `live_dependencies.py`)
- Performance workload seeds present in the catalog (see `recommendation_workloads.py`)

## Run

```bash
python scripts/run_recommendation_serving_performance_benchmark.py
```

Or:

```bash
pytest tests/serving/test_recommendation_serving_performance_production.py -q
```

Artifacts are environment-specific; do not treat latency numbers as CI gates.
