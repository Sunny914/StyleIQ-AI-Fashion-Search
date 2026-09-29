# Phase 12.5 — Baseline Search Evaluation

**Status:** Baseline measurement artifacts (Phase 12.6+ experiments and comparisons)  
**Benchmark:** `productiq_search_benchmark_v1` v1.0.0 (Phase 12.2, unmodified)

## Purpose

Execute **real** ProductIQ retrieval implementations through the Phase **12.4** runner and persist **`SearchVariantEvaluationResult`** artifacts for each supported baseline variant. This phase **does not** select winners, optimize retrieval, or run significance tests.

```text
productiq_search_benchmark_v1
        ↓
SearchEvaluationRequest + SearchEvaluationVariantExecutor
        ↓
run_search_evaluation (12.4)
        ↓
evaluate_search_variant_metrics (12.3)
        ↓
baseline run JSON artifact
```

## Supported baseline variants

| Key | Implementation | Variant name |
|-----|----------------|--------------|
| `bm25` | `BM25Retriever` via persisted index or benchmark-scoped slice | `productiq_search_baseline_bm25` |
| `semantic` | `SemanticRetriever` (BGE + pgvector HNSW) | `productiq_search_baseline_semantic` |
| `rrf` | `RRFHybridRetriever` (BM25 + semantic, `RRFConfig.rank_constant=60`) | `productiq_search_baseline_rrf` |

Variant **version** strings come from repository manifests where available (BM25/vector index `schema_version` **1.0.0**). RRF baseline variant version **1.0.0** documents the evaluation harness revision; fusion uses `DEFAULT_RRF_RANK_CONSTANT` **60**.

## Execution configuration

Default baseline metrics (explicit, not inherited from individual retrievers):

| Setting | Value |
|---------|--------|
| `k_values` | `(1, 5, 10, 20, 50)` |
| `execution_top_k` | **50** |
| `evaluation_top_k` | **50** |
| `min_relevant_grade` | **2** |
| `compute_ndcg` | **true** |

`execution_top_k` is passed to retrievers; `evaluation_top_k` is consumed only by the 12.3 metric layer.

## Artifacts

Written under `resources/evaluation/`:

| Variant | File |
|---------|------|
| BM25 | `productiq_search_benchmark_v1_baseline_bm25_run.json` |
| Semantic | `productiq_search_benchmark_v1_baseline_semantic_run.json` |
| RRF | `productiq_search_benchmark_v1_baseline_rrf_run.json` |

Each artifact includes:

- `artifact_schema_version` **12.5.0**
- benchmark + variant identity
- `execution_configuration`
- `retrieval_provenance` (manifests, index mode, RRF constant, etc.)
- full `evaluation_result` (lineage, **per-query** metrics, aggregate)
- `deterministic_checksum_sha256` (excludes `runtime_metadata`)
- optional `historical_reference` (Phase 4.8 / 4.14 / 4.16 runs — descriptive only)
- `runtime_metadata` (duration, query counts — non-deterministic)

## Running

```bash
python scripts/run_search_baseline_evaluation.py
python scripts/run_search_baseline_evaluation.py --variants bm25
```

Environment:

- `PRODUCTIQ_SEARCH_BASELINE_BM25_SCOPED=1` — force benchmark-scoped BM25 slice (same pattern as Phase 4.8 fallback).

Semantic and RRF require database + pgvector (same as Phase 4.14/4.16 scripts).

## Historical cross-check

Phase 12.5 artifacts may embed **`historical_reference`** blocks pointing at legacy run JSON files. These are **not** used to overwrite or reconcile Phase 12 numbers and **do not** declare a best variant.

## Phase 12.6+ deferral

Multi-variant experiment comparison, significance, failure analysis, and reporting build on these baseline artifacts — not in 12.5.

## Related docs

- `docs/architecture/search-evaluation-runner.md`
- `docs/architecture/search-evaluation-metrics.md`
- `docs/architecture/search-benchmark-artifact.md`
