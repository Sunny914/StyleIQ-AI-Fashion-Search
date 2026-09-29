# Phase 12.4 — Search Evaluation Runner

**Status:** Orchestration layer (Phase 12.5+ runs real baseline variants)  
**Depends on:** Phase 12.1 contracts, 12.2 benchmark, 12.3 metrics

## Purpose

The runner connects **benchmark queries**, a **pluggable search variant executor**, and the **Phase 12.3 metric layer** to produce a **`SearchVariantEvaluationResult`** without embedding BM25, semantic, RRF, or ranking logic.

```text
SearchEvaluationRequest
        ↓
SearchEvaluationRunner.run(request, executor)
        ↓
for each benchmark query (sorted by query_id):
        executor.execute_query(query, context)
        ↓
        SearchRankedResultsForQuery
        ↓
evaluate_search_variant_metrics (12.3)
        ↓
SearchVariantEvaluationResult
```

## Variant execution abstraction

**`SearchEvaluationVariantExecutor`** (protocol) defines one method:

- **`execute_query(query, context) -> SearchRankedResultsForQuery`**

Implementations are injected (dependency inversion). The runner never branches on variant name or retrieval mode.

| Helper | Role |
|--------|------|
| **`MappingSearchEvaluationExecutor`** | Deterministic fixed rankings (tests, notebooks) |
| **`RetrieverSearchEvaluationExecutor`** | Thin adapter over generic **`Retriever`** (no 12.5 wiring) |

**`SearchEvaluationRunContext`** exposes the frozen **`SearchEvaluationRequest`**, benchmark, variant, metric configuration, and **`execution_top_k`**.

## Query lifecycle

1. Benchmark queries are iterated in **sorted `query_id` order**.
2. Each query is executed once; the returned **`query_id`** must match the benchmark row.
3. Ranked IDs are validated by Pydantic + 12.3 rules (no empty IDs, no duplicates).
4. **Empty rankings** (`ranked_product_ids=()`) are valid outcomes and flow into metrics as zero-hit prefixes.
5. **Execution exceptions** propagate as **`RetrievalError`** with benchmark query and variant identity in the message — never converted to empty rankings.

## Query coverage

After execution, **`evaluate_search_variant_metrics`** enforces:

- no missing benchmark queries
- no extra unknown query IDs
- no duplicate result rows

The runner does not skip queries or synthesize placeholder rankings.

## Execution vs evaluation top-K

| Field | Owner | Meaning |
|-------|--------|---------|
| **`execution_top_k`** | **`SearchMetricConfiguration`** (12.4) | Passed to executors via context; caps how many IDs the variant should retrieve |
| **`evaluation_top_k`** | **`SearchMetricConfiguration`** (12.3) | Metric layer truncates rankings before P/R/HitRate/MRR/nDCG |

Defaults: **`execution_top_k = 50`** (`DEFAULT_RETRIEVAL_EVALUATION_TOP_K`), **`evaluation_top_k = 10`**.

## Metric integration

The runner **does not** implement metric formulas. It delegates to **`evaluate_search_variant_metrics`**, which calls **`compute_search_query_metrics`** and **`aggregate_search_query_metrics`**.

## Lineage

**`_apply_request_lineage`** copies from the request into the result:

- **`evaluation_version`**
- full **`metric_configuration`** (including `execution_top_k`)
- benchmark catalog provenance and variant **`lineage_labels`** (via 12.3 lineage builder)

No timestamps are added.

## Determinism

Same request + deterministic executor → identical serialized **`SearchVariantEvaluationResult`** (stable query order, sorted metric keys in JSON).

## Phase 12.5 deferral

12.4 establishes the execution boundary only. Baseline BM25/semantic/RRF benchmark runs, experiment artifacts, and reporting are **12.5+** — they will supply concrete **`SearchEvaluationVariantExecutor`** implementations and call **`run_search_evaluation`**.

## API

- **`run_search_evaluation(request, executor)`**
- **`SearchEvaluationRunner().run(request, executor)`**

## Related docs

- `docs/architecture/search-evaluation-contract.md`
- `docs/architecture/search-benchmark-artifact.md`
- `docs/architecture/search-evaluation-metrics.md`
