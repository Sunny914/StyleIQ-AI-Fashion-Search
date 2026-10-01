# ProductIQ serving performance benchmarks (Phase 13.8)

This tree holds **measurement artifacts** and **pinned baselines** for HTTP serving
performance. It is separate from Phase 12 search **relevance** evaluation under
`resources/evaluation/`.

## Safe by default

Normal application startup and default pytest runs **do not** execute production
benchmarks or require PostgreSQL, BM25, embeddings, or full catalog artifacts.

Production benchmarks are **opt-in** via `PRODUCTIQ_*` environment variables (see
`serving-performance-architecture.md` §13.8.9).

## Layout

| Directory | Phase | Purpose |
|-----------|-------|---------|
| `search_serving/` | 13.8.3 | Search serving run JSON (production pending in this repo) |
| `recommendation_serving/` | 13.8.4 | Recommendation serving runs (production pending) |
| `product_serving/` | 13.8.5 | Product/catalog serving runs (local measurements present) |
| `concurrency/` | 13.8.6 | Concurrency sweep JSON (product measured; search/rec pending) |
| `baselines/` | 13.8.7 | Pinned baseline records (explicit pin only) |

Final audit: `serving_performance_phase_13_8_final_audit.json` / `.md`.

Phase 13.9 observability final audit: `observability_phase_13_9_final_audit.json` / `.md`
(regenerate: `python scripts/run_observability_phase_13_9_audit.py`).

Phase 13 final production serving audit: `production_serving_phase_13_10_final_audit.json` / `.md`
(regenerate: `python scripts/run_production_serving_phase_13_10_audit.py`).

Phase 14 deployment foundation audit: `phase_14_deployment_foundation_audit.json` / `.md`
(regenerate: `python scripts/run_phase_14_deployment_foundation_audit.py`).

## How to run

Synthetic/unit coverage:

```bash
python -m pytest tests/serving/test_serving_performance_contract.py tests/serving/test_serving_performance_runner.py -q
```

Product production benchmark (requires processed catalog parquet):

```bash
set PRODUCTIQ_PRODUCT_SERVING_PERFORMANCE_BENCHMARK=1
python scripts/run_product_serving_performance_benchmark.py
```

Search / recommendation production benchmarks require PostgreSQL + retrieval smoke flags
(see per-directory README).

Concurrency sweep:

```bash
set PRODUCTIQ_SERVING_CONCURRENCY_BENCHMARK=1
python scripts/run_serving_concurrency_benchmark.py
```

## Compare against a baseline

1. Pin a baseline with `pin_run_result_as_baseline()` (13.8.7) or place JSON under `baselines/`.
2. Run:

```bash
python scripts/compare_serving_performance.py --baseline PATH --current PATH
```

Optional threshold policy JSON and `--fail-on-incompatible` / `--fail-on-regression-flags`.

## Evidence and audit

```bash
python scripts/analyze_serving_performance_evidence.py
python scripts/run_serving_performance_phase_13_8_audit.py
```

Do not fabricate measurements or mark pending production runs as complete.
