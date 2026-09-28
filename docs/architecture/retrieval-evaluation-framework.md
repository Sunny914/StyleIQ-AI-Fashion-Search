# Unified Retrieval Evaluation Framework (Phase 4.18)

**Status:** Implemented  
**Implements:** Retriever-agnostic measurement contract, artifact replay, category aggregation, run comparison, lineage  
**Does not implement:** Retrieval optimization, Phase 4.19+

## Purpose

Phase 4.18 defines **how** ProductIQ measures retrieval quality. It does not change BM25, semantic, hybrid, or RRF retrieval logic, and does not change metric formulas established in Phase 4.8.

## Architecture

```text
LexicalRetrievalBenchmark (judgments + categories)
        ↓
 retrieved_product_ids per query  ← live Retriever OR stored run artifact
        ↓
 evaluate_single_query()  →  metrics.py (unchanged definitions)
        ↓
 macro aggregate + category aggregate
        ↓
 EvaluationResult + EvaluationLineage
        ↓
 optional EvaluationComparisonResult
```

### Modules

| Module | Role |
|--------|------|
| `unified_evaluation_schema.py` | Pydantic contracts |
| `unified_evaluator.py` | `UnifiedRetrievalEvaluator`, aggregation |
| `unified_comparison.py` | Compatible-run comparison (deltas only) |
| `unified_reporting.py` | Artifact replay for BM25 / semantic / RRF |
| `metrics.py` | Canonical P@K, R@K, MRR (Phase 4.8) |

## Metric definitions (preserved)

**Precision@K:** relevant hits in top-K ÷ `min(K, len(retrieved))`; 0 when nothing retrieved.

**Recall@K:** relevant hits in top-K ÷ judged relevant count; `None` per-query when judged set empty; macro recall excludes ineligible queries (Phase 4.8 behavior).

**MRR (macro):** mean of per-query reciprocal rank; 0 when no judged hit in list.

**Macro aggregation:** unweighted mean across benchmark queries (not micro over products).

## Incomplete ground truth

Judged `relevant_product_ids` are a **curated subset**. Unjudged catalog products are not negatives. All limitations from the benchmark JSON are copied into evaluation lineage.

## Live vs artifact evaluation

- **Live:** `UnifiedRetrievalEvaluator.evaluate(benchmark, retriever)` calls `Retriever.retrieve` only.
- **Artifact:** Recomputes metrics from stored `retrieved_product_ids` (official Phase 4.8 / 4.14 / 4.16 runs) without modifying source files.

## Comparison semantics

`compare_evaluation_results(a, b)` requires matching benchmark name/version, `retrieval_top_k`, and `k_values`. Outputs absolute and relative deltas for macro metrics. Does **not** declare winners.

When RRF lineage includes scoped BM25, comparisons involving RRF are **descriptive only** (configuration mismatch vs full-catalog BM25).

## Lineage

`EvaluationLineage` records known metadata only: benchmark identity, system name, retrieval method, top-K, K values, artifact paths, BM25 index mode, embedding model fields, RRF constants, limitations. Missing fields remain null.

## Artifacts

```bash
python scripts/run_unified_retrieval_evaluation.py
```

| File | Content |
|------|---------|
| `retrieval_evaluation_v1.json` | Catalog: BM25, semantic, RRF evaluations + comparisons |
| `retrieval_evaluation_v1.jsonl` | Per system × query metric rows |
| `retrieval_comparison_v1.json` | Comparison deltas |

Official Phase 4.8/4.14/4.16 run files are **not** overwritten.

## Determinism

Queries, categories, and per-query rows are sorted deterministically. Given identical retrieved lists and benchmark, metrics match Phase 4.8 evaluator output (validated against `lexical_retrieval_benchmark_v1_run.json`).

## Known limitation: Phase 4.16 RRF

RRF evaluation in the unified catalog uses `hybrid_rrf_benchmark_v1_run.json` with **scoped BM25** live fusion on this machine. Do not treat RRF vs full-catalog BM25 artifact metrics as a controlled experiment.

## Notebook

`notebooks/data_engineering/35_retrieval_evaluation_framework.ipynb`

## Scope boundary

**Out of scope:** retrieval fixes, embedding regeneration, index rebuilds, **Phase 4.19 / 4.20**.
