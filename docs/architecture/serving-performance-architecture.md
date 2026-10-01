# Phase 13.8.1 — Serving Performance Contract & Benchmark Architecture

**Status:** Contract / architecture only (measure first, optimize second)  
**Scope:** HTTP serving latency & throughput — **not** search/recommendation relevance evaluation

## Principle

```text
MEASURE FIRST → OPTIMIZE SECOND (Phase 13.8.2+)
```

Phase 13.8.1 does **not** add Redis, caching, async rewrites, pool tuning, model changes, or algorithm edits.

## Performance boundaries

### Search (`POST /api/v1/search`)

| Layer | Stages (conceptual) |
|-------|---------------------|
| **A. End-to-end HTTP** | Client → FastAPI → response bytes |
| **B. Service** | `SearchServingService.search()` |
| **C. Internal stages** | validation → query representation → retrieval → filtering/RRF → ranking → API mapping → serialization |

Stage **C** is recorded only when explicit instrumentation exists (`ServingStageMeasurement` on results). This sub-phase defines the contract; it does not instrument pipelines.

### Recommendation (`POST /api/v1/recommendations`)

HTTP → validation → seed resolution → candidate generation → similarity → features → ranking → selection → mapping → serialization.

### Product (`GET /api/v1/products/{product_id}`)

HTTP → validation → catalog lookup → mapping → serialization.

### Health / readiness

Out of scope for default workloads; endpoints exist for liveness/readiness, not primary latency SLOs in 13.8.1.

## Benchmark types

| Type | Measures |
|------|----------|
| `api` | Full HTTP request/response (TestClient or HTTP client) |
| `service` | Serving protocol method only (no HTTP stack) |
| `concurrency` | Controlled parallel workers (`concurrency` ≥ 1) |
| `production_smoke` | Opt-in smoke path aligned with existing `PRODUCTIQ_*_SMOKE` flags — not load testing |

Boundaries are explicit in `ServingBenchmarkConfiguration.benchmark_type`.

## Workload model

Deterministic workloads live in `productiq.serving.performance.workloads`:

- `serving_search_minimal_v1`
- `serving_recommendation_minimal_v1`
- `serving_product_minimal_v1`

Each workload specifies route, method, JSON body or path parameters, and endpoint identity. This is **not** the Phase 12 search relevance benchmark.

## Measurement statistics

Latency: **milliseconds** with `min`, `p50`, `p95`, `p99`, `max`, and `mean` (`LatencyStatistics`).

Throughput: optional **requests_per_second** (`ThroughputStatistics`).

Errors: `BenchmarkErrorSummary` (`error_count`, `total_attempts`, `error_rate`).

**No latency SLOs or winners** in 13.8.1.

## Environment metadata

`ServingEnvironmentMetadata`: Python version, platform, contract version, ProductIQ package version, optional hostname.

`ServingConfigurationMetadata`: `ServingConfig`-aligned fields (`api_version`, `api_max_top_k`, `service_name`) plus optional artifact identifier map.

Collection is lightweight and deterministic where possible (hostname optional).

## Result artifact

`ServingBenchmarkRunResult` — JSON-serifiable, validated Pydantic model:

- configuration + workload identity
- latency (+ optional throughput)
- errors
- environment + serving configuration
- provenance (`benchmark_run_id`, `recorded_at_utc`, runner metadata)
- optional `stage_measurements`

Contract version: `SERVING_PERFORMANCE_CONTRACT_VERSION` (`1.0.0`).

## Reproducibility checklist

Document every run with:

1. What was measured (benchmark type + endpoint)
2. Workload id/name and payload
3. Warmups and iterations
4. Concurrency
5. Application / `ServingConfig` snapshot
6. Artifact/model identifiers (when production stacks are used)
7. Software versions (ProductIQ, contract)
8. Environment (Python, OS)

Absolute milliseconds are **not** comparable across hardware. Relative deltas are for the same environment/workload only.

## Regression comparison

`compare_serving_benchmark_runs(baseline, comparison)` → `ServingBenchmarkComparison`:

- absolute latency deltas (ms)
- relative percent deltas where baseline ≠ 0
- optional throughput delta

No automatic pass/fail thresholds; no variant ranking.

## Relationship to Phase 13.7

Phase 13.7 proves **correctness** (contracts, errors, isolation) with deterministic fakes.

Phase 13.8 measures **latency/throughput** using separate contracts — performance results must not mix with nDCG/MRR evaluation artifacts.

## Relationship to Phase 13.9 (future)

Observability (metrics, tracing hooks) may populate `stage_measurements` and external telemetry. 13.8.1 only reserves schema fields.

## Non-goals (13.8.1)

- Optimization, caching, Redis, infra changes
- Large benchmark datasets
- Production load tests
- Relevance/quality metrics in performance results
- Cross-machine SLO enforcement

## Benchmark execution (Phase 13.8.2)

### Runner

`run_serving_benchmark()` in `serving/performance/runner.py`:

1. Validate configuration/workload identity  
2. Run `warmups` discarded executions  
3. Run `iterations` measured executions (respecting `concurrency`)  
4. Build `ServingBenchmarkRunResult` with provenance  

Runner version: `BENCHMARK_RUNNER_VERSION` (`1.0.0`).

### Timing

Uses `time.perf_counter()` via `PerfCounterTimer` (monotonic, high resolution). Elapsed latency is **not** derived from wall-clock timestamps. Tests may inject `ScriptedTimer`.

### Warmups vs iterations

Only the **M measured iterations** contribute to latency statistics. Warmup executions are counted separately by the driver (not stored on the result artifact) and never appear in latency samples.

### Latency statistics

Computed by `compute_latency_statistics_ms()` / `LatencyStatistics.from_samples_ms()` on **successful** executions only. Percentiles use linear interpolation on sorted samples (documented in `statistics.py`). Failed executions are excluded; all failures yield `latency: null` on the result.

### Error accounting

`BenchmarkErrorSummary` records `success_count`, `error_count`, `total_attempts`, and `error_rate`. Internal exceptions are caught by the runner and counted as errors without exposing raw messages in the artifact.

### Throughput

`calculate_throughput_rps(success_count, wall_seconds)` where `wall_seconds` is the monotonic duration of the **measured** phase (start before first measured execution through completion of the last). Denominator is **not** the sum of per-request latencies. For concurrent runs, throughput still uses total successful requests over overall measured wall time.

### Executors

| Executor | Entry | Boundary |
|----------|-------|----------|
| API | `run_api_benchmark` / `run_api_benchmark_app` | FastAPI `TestClient` HTTP request/response |
| Service | `run_service_benchmark` | `SearchServingService` / `RecommendationServingService` / `ProductServingService` methods |

API latency minus service latency is **not** guaranteed to equal HTTP overhead; they are separate benchmark boundaries.

### Concurrency

`concurrency=1`: sequential measured iterations.  
`concurrency>1`: `ThreadPoolExecutor(max_workers=concurrency)` submits `iterations` tasks; results collected thread-safely via futures. Accounting must satisfy `success_count + error_count == iterations`.

### Environmental variability

Absolute latency and throughput vary by CPU load, interpreter, and host. The harness is deterministic in **accounting**; injected timers support unit tests without asserting real-world millisecond values.

## Code map

| Module | Role |
|--------|------|
| `serving/performance/schema.py` | Contracts |
| `serving/performance/workloads.py` | Default workloads |
| `serving/performance/statistics.py` | Percentile helpers |
| `serving/performance/timing.py` | Monotonic timer + test doubles |
| `serving/performance/runner.py` | Warmup/iteration engine |
| `serving/performance/executors/api.py` | HTTP benchmark executor |
| `serving/performance/executors/service.py` | Service benchmark executor |
| `serving/performance/comparison.py` | Baseline vs new run deltas |
| `tests/serving/test_serving_performance_contract.py` | Contract tests |
| `tests/serving/test_serving_performance_runner.py` | Harness tests |
| `serving/performance/search_workloads.py` | Search performance workloads |
| `serving/performance/search_benchmark.py` | Production search benchmark suite |
| `serving/performance/recommendation_workloads.py` | Recommendation performance workloads |
| `serving/performance/recommendation_benchmark.py` | Production recommendation benchmark suite |
| `serving/performance/recommendation_production_wiring.py` | Live RecommendationPipeline assembly |
| `tests/serving/test_search_serving_performance_benchmark.py` | Offline search benchmark tests |
| `tests/serving/test_search_serving_performance_production.py` | Opt-in production search benchmark |
| `tests/serving/test_recommendation_serving_performance_benchmark.py` | Offline recommendation benchmark tests |
| `serving/performance/product_workloads.py` | Product performance workloads |
| `serving/performance/product_benchmark.py` | Production product benchmark suite |
| `tests/serving/test_product_serving_performance_benchmark.py` | Offline product benchmark tests |
| `tests/serving/test_product_serving_performance_production.py` | Opt-in production product benchmark |
| `serving/performance/concurrency_benchmark.py` | Concurrency sweep orchestration |
| `serving/performance/concurrency_schema.py` | Sweep result contracts |
| `tests/serving/test_serving_concurrency_benchmark.py` | Offline concurrency tests |
| `tests/serving/test_serving_concurrency_benchmark_production.py` | Opt-in product concurrency sweep |

Notebook: `notebooks/data_engineering/73_serving_performance_contract.ipynb`

## Search serving production benchmark (Phase 13.8.3)

### Architecture

Uses the **real** production search path:

- `ProductionRetrievalPipeline.retrieve_ranked` (BM25 + pgvector semantic + RRF + hard filtering + baseline ranking)
- `ProductionSearchServingService` via `create_search_serving_service_from_pipeline`
- FastAPI `create_app(search_service=...)` for API boundary benchmarks

No parallel fake pipeline for production runs. In-memory ranked pipelines are used only in offline harness tests.

### Workloads

Catalog: `search_workloads.py` (`SEARCH_SERVING_PERFORMANCE_WORKLOADS`, version `1.0.0`):

| workload_id | Intent |
|-------------|--------|
| `search_serving_lexical_v1` | Short lexical query |
| `search_serving_brand_v1` | Brand query |
| `search_serving_attribute_v1` | Multi-attribute query |
| `search_serving_natural_v1` | Natural-language query |
| `search_serving_filter_v1` | Query + structured filters |

Separate from Phase 12 relevance evaluation benchmarks.

### Warmup methodology

`SearchServingBenchmarkSettings` defaults: **5 warmups**, **30 iterations**, **concurrency=1**.

The production stack (pipeline + app + service) is constructed **once** per suite; warmups discard timings before measured iterations (steady-state).

### Production dependencies

- PostgreSQL + pgvector embeddings (≥1000 rows for integration gate)
- BM25: full `bm25_lexical_index.pkl` or benchmark-scoped fallback (`live_dependencies.py`)
- BGE encoder (CPU) for semantic retrieval
- Existing flags: `PRODUCTIQ_RUN_INTEGRATION_TESTS=1`, `PRODUCTIQ_PRODUCTION_RETRIEVAL_SMOKE=1`
- Opt-in benchmark flag: `PRODUCTIQ_SEARCH_SERVING_PERFORMANCE_BENCHMARK=1`

### Execution

- Suite: `run_search_serving_performance_suite()` in `search_benchmark.py`
- CLI: `scripts/run_search_serving_performance_benchmark.py`
- Pytest: `tests/serving/test_search_serving_performance_production.py`

### Artifacts

Written to `resources/benchmark/search_serving/`:

- Per-run JSON (`ServingBenchmarkRunResult`)
- Suite summary JSON
- Descriptive Markdown report (no ranking of workloads)

Checksums recorded when `bm25_lexical_index.manifest.json` is present; never fabricated.

### Stage instrumentation

`stage_measurements` remain **empty** in 13.8.3 (no intrusive pipeline changes).

### API vs service

Both boundaries are measured per workload. Differences are **not** interpreted as exact HTTP overhead.

### Limitations

- Not part of default CI
- Latency numbers are environment-specific
- See §13.8.6 for concurrency sweeps

## Recommendation serving production benchmark (Phase 13.8.4)

### Architecture

Uses the **real** production recommendation path:

- `RecommendationPipeline.recommend` (vector + attribute + BM25 generators, content similarity, baseline ranker, selection)
- `ProductionRecommendationServingService` via `create_recommendation_serving_service_from_pipeline`
- FastAPI `create_app(recommendation_service=...)` for API boundary benchmarks

Production assembly: `recommendation_production_wiring.build_production_recommendation_pipeline`.
No benchmark-specific pipeline fork. In-memory pipelines are used only in offline harness tests.

### Workloads

Catalog: `recommendation_workloads.py` (`RECOMMENDATION_SERVING_PERFORMANCE_WORKLOADS`, version `1.0.0`):

| workload_id | Seed product ID | Intent |
|-------------|-----------------|--------|
| `recommendation_serving_brand_activity_v1` | `460946942002` | Nike running (evaluation brand_activity) |
| `recommendation_serving_brand_activity_alt_v1` | `460825114005` | Alternate Nike running seed |
| `recommendation_serving_brand_color_v1` | `469193981005` | Black Nike (brand_color) |
| `recommendation_serving_material_v1` | `441123902006` | Material-focused seed |
| `recommendation_serving_filter_v1` | `460946942002` | SIMILAR + structured filters |

All workloads use `recommendation_type=similar` and `top_k=10`. Candidate pool sizing follows production `RecommendationConfig` defaults (`candidate_pool_top_k=50`) unless the API later exposes overrides.

Seed IDs are shared with the Phase 11 evaluation benchmark metadata but the performance catalog is a **separate**, smaller workload set.

### Warmup methodology

`RecommendationServingBenchmarkSettings` defaults: **5 warmups**, **30 iterations**, **concurrency=1**.

The production stack (pipeline + app + service) is constructed **once** per suite; warmups discard timings before measured iterations.

### Production dependencies

- PostgreSQL catalog rows for workload seeds (validated before the suite)
- pgvector seed embeddings (validated before the suite)
- PostgreSQL + pgvector for vector candidate generation and similarity batch loads
- BM25: full `bm25_lexical_index.pkl` or benchmark-scoped fallback (`live_dependencies.py`)
- BGE encoder (CPU) for semantic retriever / vector index wiring
- Existing flags: `PRODUCTIQ_RUN_INTEGRATION_TESTS=1`, `PRODUCTIQ_PRODUCTION_RETRIEVAL_SMOKE=1`
- Opt-in benchmark flag: `PRODUCTIQ_RECOMMENDATION_SERVING_PERFORMANCE_BENCHMARK=1`

### Execution

- Suite: `run_recommendation_serving_performance_suite()` in `recommendation_benchmark.py`
- CLI: `scripts/run_recommendation_serving_performance_benchmark.py`
- Pytest: `tests/serving/test_recommendation_serving_performance_production.py`

### Artifacts

Written to `resources/benchmark/recommendation_serving/`:

- Per-run JSON (`ServingBenchmarkRunResult`)
- Suite summary JSON
- Descriptive Markdown report

Checksums recorded when `bm25_lexical_index.manifest.json` and/or `product_representations.manifest.json` are present; never fabricated.

### Stage instrumentation

`stage_measurements` remain **empty** in 13.8.4 (no intrusive pipeline changes).

### API vs service

Both boundaries are measured per workload. Differences are **not** interpreted as exact HTTP overhead.

### Limitations

- Attribute candidate generation lists the production catalog each request (measured, not optimized in this phase)
- Not part of default CI
- Latency numbers are environment-specific
- See §13.8.6 for concurrency sweeps

## Product serving production benchmark (Phase 13.8.5)

### Architecture

Uses the **real** product read path:

- `ProcessedParquetProductCatalogReadProvider` over `resources/processed/product_catalog.parquet` (index built once at provider construction)
- `ProductionProductServingService.get_product` via `create_product_serving_service_from_catalog`
- FastAPI `create_app(product_service=...)` for API boundary benchmarks

No alternate catalog implementation. In-memory providers are used only in offline harness tests.

### Workloads

Catalog: `product_workloads.py` (version `1.0.0`):

| workload_id | product_id | Role |
|-------------|------------|------|
| `product_serving_existing_v1` | `460946942002` | Primary existing product |
| `product_serving_existing_alt_v1` | `460825114005` | Alternate existing product |
| `product_serving_existing_rich_v1` | `441118465014` | Populated public fields |
| `product_serving_missing_v1` | `productiq_perf_missing_v1` | Expected 404 (excluded from latency suite) |

The primary suite benchmarks **existing products only**. The missing workload validates functional 404 semantics separately; the generic runner still counts HTTP `>=400` as benchmark errors for that workload.

### Initialization methodology

1. Construct `ProcessedParquetProductCatalogReadProvider` once (Parquet → in-memory index)
2. Construct `ProductionProductServingService` once
3. Construct FastAPI app once
4. Warmups, then measured iterations

One-time Parquet load is **not** included in per-request latency samples.

### Warmup methodology

`ProductServingBenchmarkSettings` defaults: **5 warmups**, **30 iterations**, **concurrency=1**.

### Production dependencies

- `resources/processed/product_catalog.parquet` on disk
- Opt-in flag: `PRODUCTIQ_PRODUCT_SERVING_PERFORMANCE_BENCHMARK=1`
- No PostgreSQL requirement

### Execution

- Suite: `run_product_serving_performance_suite()` in `product_benchmark.py`
- CLI: `scripts/run_product_serving_performance_benchmark.py`
- Pytest: `tests/serving/test_product_serving_performance_production.py`

### Artifacts

Written to `resources/benchmark/product_serving/`:

- Per-run JSON (`ServingBenchmarkRunResult`)
- Suite summary JSON
- Descriptive Markdown report

Checksum recorded when `product_catalog.manifest.json` is present; never fabricated.

### Stage instrumentation

`stage_measurements` remain **empty** in 13.8.5.

### API vs service

Both boundaries measured for successful existing-product workloads. Differences are **not** interpreted as exact HTTP overhead.

### Limitations

- Not part of default CI
- Latency numbers are environment-specific

## Serving concurrency & throughput (Phase 13.8.6)

### Design

Orchestration in `concurrency_benchmark.py` reuses `run_serving_benchmark()` from 13.8.2 with
`ServingBenchmarkType.CONCURRENCY`. For each endpoint, the **same workload** is measured at
concurrency levels **1, 2, 4, 8** (default), with **independent warmups** at every level.

### Workloads (reused)

| Endpoint | workload_id |
|----------|-------------|
| Search | `search_serving_lexical_v1` |
| Recommendation | `recommendation_serving_brand_activity_v1` |
| Product | `product_serving_existing_v1` |

### Boundaries

- **API:** FastAPI `TestClient` via `run_api_benchmark`
- **Service:** `run_service_benchmark` on production serving services

Results are labeled separately; API minus service is **not** reported as HTTP overhead.

### Throughput

Per level: `success_count / measured_wall_seconds` (same as 13.8.2).

### Schema

Individual runs: `ServingBenchmarkRunResult`. Sweep aggregate: `ConcurrencyBenchmarkSweepResult`
(`concurrency_schema.py`).

### Thread safety

Documented in `thread_safety_audit.py` and copied into sweep artifacts. No production locks or
pools were added for benchmarking.

### Production execution

- Flag: `PRODUCTIQ_SERVING_CONCURRENCY_BENCHMARK=1`
- Product sweep: processed catalog parquet only
- Search/recommendation sweeps: require 13.8.3 / 13.8.4 production prerequisites (pending)

### Artifacts

`resources/benchmark/concurrency/` — sweep JSON, summary JSON, Markdown table (no winners).

### Limitations

- Descriptive only; no optimal concurrency selection
- Environment-specific latency and throughput

## Performance baseline & regression (Phase 13.8.7)

### Objective

Pin benchmark results as baselines, compare new runs deterministically, and optionally
apply explicit threshold policies. Default behavior is **descriptive** (deltas only), not
automatic pass/fail.

### Baseline contract

`ServingPerformanceBaselineRecord` (`baseline_schema.py`) wraps:

- `BenchmarkRunIdentity` (endpoint, workload_id, benchmark_boundary, concurrency, warmups, iterations)
- environment + serving configuration metadata
- embedded `ServingBenchmarkRunResult`
- baseline contract version + serving performance contract version

Storage: `resources/benchmark/baselines/{search,recommendation,product,concurrency}/`.
Updates require explicit `overwrite=True` in `pin_baseline_record()`.

### Identity & lookup

Comparison requires matching identity fields. Unrelated workloads or API vs service boundaries
are not silently compared. Lookup: `find_baseline_by_identity()` returns `BASELINE_NOT_FOUND`
when no exact identity match exists.

### Provenance compatibility

Before metrics, `assess_provenance_compatibility()` checks identity, performance contract version,
runner version, and shared `artifact_identifiers` keys. Material mismatches yield
`compatible=false` with explicit `mismatches`. Environment/platform differences may appear as
informational `provenance_differences` without blocking when core checks pass.

### Metric comparison

Reuses `compare_serving_benchmark_runs()` for core latency pairing, plus extended report fields:

- Latency: min, mean, p50, p95, p99, max (absolute ms and relative % where baseline ≠ 0)
- Throughput: optional RPS deltas
- Reliability: success/error counts and error_rate deltas

No winners; no statistical significance claims in 13.8.7.

### Threshold policy

Optional `PerformanceThresholdPolicy` (latency p95 relative/absolute, throughput relative
decrease, error_rate absolute increase). Observations are labeled **OBSERVATION**;
breaches set `regression_flag=true` and populate `regression_flags` — only when a policy is
configured.

### CLI

`scripts/compare_serving_performance.py --baseline PATH --current PATH`
Optional `--threshold-policy`, `--fail-on-incompatible`, `--fail-on-regression-flags`.

### Limitations

- No significance testing (later phase)
- Baselines are configuration-specific; portability across environments is not implied

## Evidence-based optimization (Phase 13.8.8)

### Principle

Measure first, optimize second. No Redis, async rewrites, database changes, or algorithm edits
without benchmark evidence tying a change to an observed bottleneck.

Workflow:

```text
evidence inventory → bottleneck analysis → hypothesis → (optional) single change
→ baseline (13.8.7) → benchmark → comparison → regression tests
```

Phase 13.8.8 **did not retain a production optimization** because required evidence was missing
or inconclusive (see blockers below).

### Available evidence (repository state)

| Source | Status |
|--------|--------|
| 13.8.3 search serving | No production `ServingBenchmarkRunResult` JSON in `resources/benchmark/search_serving/` |
| 13.8.4 recommendation serving | No production run JSON in `resources/benchmark/recommendation_serving/` |
| 13.8.5 product serving | Real local run `7c60fd3a-f882-4cca-a7a9-1e189976e7cf` |
| 13.8.6 product concurrency | Sweeps under `resources/benchmark/concurrency/` |
| 13.8.7 baselines | Infrastructure only; no pinned baseline JSON required for this decision |
| Stage instrumentation | Empty on existing serving runs |

### Bottleneck analysis (classification)

**OBSERVED**

- Product catalog: Parquet loaded once; in-memory O(1) lookup (`lookup: in_memory_index_o1` in 13.8.5 artifacts).
- Product service latency: ~0.005 ms mean for `product_serving_existing_v1` (run `7c60fd3a-…`, service boundary, c=1).
- Product API vs service: API mean ~5.57 ms vs service ~0.005 ms for the same workload (same run); gap not decomposed (no `stage_measurements`).
- Product concurrency sweeps recorded for API and service boundaries.

**POTENTIAL**

- Recommendation attribute generation calls `list_catalog_products()` per request (`attribute.py`). Architectural fact only — **not** established as the dominant recommendation serving bottleneck without 13.8.4 production measurements.

**UNKNOWN**

- Search production serving latency (13.8.3 artifacts absent).
- Recommendation production serving latency (13.8.4 artifacts absent).
- Internal stage breakdown for search, recommendation, product, or HTTP overhead attribution.

### Optimization blockers

1. **Search** — no 13.8.3 production benchmark → no evidence-based search serving change.
2. **Recommendation** — no 13.8.4 production benchmark → no evidence-based candidate-generation change.
3. **Product catalog lookup** — sub-millisecond service latency observed → no evidence that lookup is the bottleneck.
4. **API latency** — API/service gap observed but not staged → cannot target a specific production surface responsibly.

### Tooling

- `build_serving_performance_evidence_report()` in `evidence_analysis.py`
- CLI: `scripts/analyze_serving_performance_evidence.py`

Re-run 13.8.3 / 13.8.4 production benchmarks, pin baselines (13.8.7), then repeat hypothesis → single change → compare.

### Correctness & regression (this phase)

No production serving/retrieval/ranking/API behavior changes. Existing pytest/Ruff/Mypy gates apply to new analysis modules only.

### Rejected / not implemented optimizations

| Hypothesis | Result |
|------------|--------|
| Further optimize product in-memory lookup | **Rejected (not implemented)** — no observed bottleneck |
| Cache/index recommendation attribute scans | **Blocked** — no 13.8.4 baseline |
| Search retrieval tuning for serving latency | **Blocked** — no 13.8.3 baseline |

### Limitations

- Evidence report reflects artifact presence on disk; it does not fabricate missing measurements.
- Product API numbers include TestClient/HTTP stack; not a production load-test SLO.

## Performance hardening & final audit (Phase 13.8.9)

### Scope

Audit, harden, validate, and document the Phase 13.8 performance system **without** new
speculative optimizations.

### Boundaries verified

- Production serving: `src/productiq/serving/`, `src/productiq/api/`
- Performance infrastructure: `src/productiq/serving/performance/`
- Scripts: `scripts/run_*performance*` / `compare_serving_performance.py` / audit scripts
- Artifacts: `resources/benchmark/`

`create_app()` and core serving modules do **not** import `productiq.serving.performance`.

### Measurement status (implemented vs measured)

| Sub-phase | Implemented | Measured in repo |
|-----------|-------------|------------------|
| 13.8.3 search serving | Yes | **Pending** (no run JSON) |
| 13.8.4 recommendation serving | Yes | **Pending** |
| 13.8.5 product serving | Yes | **Yes** (local run `7c60fd3a-…`) |
| 13.8.6 concurrency | Yes | **Product yes**; search/recommendation sweeps **pending** |
| 13.8.7 baseline/regression | Yes | Framework only |
| 13.8.8 optimization | Yes | **No optimization retained** |
| 13.8.9 audit | Yes | This section + final audit artifacts |

`stage_measurements` remain **empty** on checked-in serving benchmark JSON.

### Final audit artifacts

- `resources/benchmark/serving_performance_phase_13_8_final_audit.json`
- `resources/benchmark/serving_performance_phase_13_8_final_audit.md`

Regenerate:

```bash
python scripts/run_serving_performance_phase_13_8_audit.py
```

### Tests

`tests/serving/test_serving_performance_phase_13_8_audit.py` covers import safety, artifact
integrity on existing product JSON, environment flag inventory, and audit report structure.

### Limitations

- Audit generation timestamp is not deterministic.
- Pending production measurements must not be reported as complete.
