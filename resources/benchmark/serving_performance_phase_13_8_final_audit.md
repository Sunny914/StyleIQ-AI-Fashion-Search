# Phase 13.8 — Serving performance final audit

- audit_version: `1.0.0`
- generated_at_utc: `2026-09-30T09:14:06.829977+00:00`

## Scope

Phase 13.8 serving performance measurement, baseline/regression, and evidence workflow.

## Sub-phases (implementation vs measurement)

| ID | Title | Implementation | Measurement | Notes |
|----|-------|----------------|-------------|-------|
| 13.8.1 | Serving performance contract | implemented | implemented | Schema + workloads; validated by contract tests. |
| 13.8.2 | Benchmark harness | implemented | implemented | Warmups excluded from latency samples; throughput uses wall clock. |
| 13.8.3 | Search serving benchmark | implemented | pending | Production measurements pending when opt-in benchmark not run. |
| 13.8.4 | Recommendation serving benchmark | implemented | pending |  |
| 13.8.5 | Product serving benchmark | implemented | measured |  |
| 13.8.6 | Concurrency sweeps | implemented | measured | Product sweeps measured locally; search/recommendation concurrency pending. |
| 13.8.7 | Baseline & regression | implemented | implemented | Framework only; pinned baseline JSON optional. |
| 13.8.8 | Evidence-based optimization | implemented | implemented | No production optimization retained. |
| 13.8.9 | Hardening & final audit | implemented | implemented |  |

## Environment flags

### `PRODUCTIQ_SEARCH_SERVING_PERFORMANCE_BENCHMARK`
- purpose: Opt-in gate for 13.8.3 production search serving benchmark pytest/script.
- prerequisites:
  - PRODUCTIQ_RUN_INTEGRATION_TESTS=1
  - PRODUCTIQ_PRODUCTION_RETRIEVAL_SMOKE=1
  - PostgreSQL/pgvector retrieval stack
- when disabled: Production search benchmark tests skip; no artifacts written.

### `PRODUCTIQ_RECOMMENDATION_SERVING_PERFORMANCE_BENCHMARK`
- purpose: Opt-in gate for 13.8.4 production recommendation serving benchmark.
- prerequisites:
  - PRODUCTIQ_RUN_INTEGRATION_TESTS=1
  - PRODUCTIQ_PRODUCTION_RETRIEVAL_SMOKE=1
  - Catalog seeds for recommendation workloads
- when disabled: Production recommendation benchmark tests skip.

### `PRODUCTIQ_PRODUCT_SERVING_PERFORMANCE_BENCHMARK`
- purpose: Opt-in gate for 13.8.5 production product serving benchmark.
- prerequisites:
  - resources/processed/product_catalog.parquet
- when disabled: Production product benchmark tests skip.

### `PRODUCTIQ_SERVING_CONCURRENCY_BENCHMARK`
- purpose: Opt-in gate for 13.8.6 concurrency sweeps (product measured; search/rec pending).
- prerequisites:
  - Endpoint-specific: product parquet and/or retrieval stack for search/rec
- when disabled: Production concurrency benchmark tests skip.

### `PRODUCTIQ_RUN_INTEGRATION_TESTS`
- purpose: Shared prerequisite for PostgreSQL-backed integration and retrieval benchmarks.
- prerequisites:
  - PostgreSQL products table with embeddings
- when disabled: Integration and retrieval-gated benchmarks skip or fail closed in tests.

### `PRODUCTIQ_PRODUCTION_RETRIEVAL_SMOKE`
- purpose: Production retrieval smoke prerequisite for search/recommendation serving benchmarks.
- prerequisites:
  - BM25/HNSW or documented fallback per live_dependencies
- when disabled: Search/recommendation production serving benchmarks skip in pytest.

## Artifact integrity

- run results validated: `36` failed: `0`
- sweeps validated: `10` failed: `0`
- checksum verifications: `36` mismatches: `0`

## Import safety

FastAPI create_app and serving services do not import productiq.serving.performance; benchmark code lives under serving/performance/ and scripts/ only.

## Test isolation

Default pytest suites skip production benchmarks unless explicit PRODUCTIQ_* flags; PostgreSQL/BM25/embeddings not required for standard serving/api/recommendation tests.

## Determinism

Workload catalogs, configurations, JSON round-trips, baseline identity, provenance checks, regression comparison, and evidence reports are covered by unit tests; timestamps/run IDs remain non-deterministic by design.

## Baseline safety

Baselines require explicit pin; overwrite=False by default; identity + provenance matching; BASELINE_NOT_FOUND without nearest-match; no fabricated search/rec baselines.

## Concurrency safety

Concurrency benchmark does not modify production code for thread safety; error accounting enforced in runner; warmups excluded from measured iterations.

## Production behavior

Phase 13.8.8 retained no optimization; performance infrastructure is isolated from search/retrieval/ranking/recommendation/product serving semantics.

## Metric semantics

Latency percentiles via compute_latency_statistics_ms; throughput = success_count/wall_seconds; relative_pct_delta returns None for zero baseline; missing throughput not coerced to zero in comparison.

## Optimization

No production optimization retained in 13.8.8 or 13.8.9.

## Stage measurements

Empty on checked-in serving benchmark artifacts.

## Outstanding measurement gaps

- Search production serving benchmark artifacts missing (13.8.3).
- Recommendation production serving benchmark artifacts missing (13.8.4).
- Search/recommendation concurrency production sweeps pending (13.8.6).
- stage_measurements empty on existing serving benchmark runs.

## Limitations

- Audit reflects repository state at generation time; pending measurements are not marked complete.
- Product API benchmark latency includes HTTP/TestClient stack.
- No statistical significance testing in Phase 13.8.

## Reproducibility

- Standard tests: python -m pytest tests/serving tests/api tests/recommendation -q
- Benchmark tests: tests/serving/test_serving_performance_*.py (synthetic) and opt-in production modules
- Compare: scripts/compare_serving_performance.py
- Evidence: scripts/analyze_serving_performance_evidence.py
- Regenerate audit: scripts/run_serving_performance_phase_13_8_audit.py
