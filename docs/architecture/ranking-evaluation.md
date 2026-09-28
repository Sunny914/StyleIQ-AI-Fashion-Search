# Phase 10.6 — Ranking Evaluation

**Status:** Implemented  
**Scope:** Offline measurement of fixed baseline ranking vs RRF order (no tuning, no LTR)

## Objective

Reproducibly measure how the **Phase 10.4 deterministic baseline ranker** (integrated in 10.5) orders benchmark queries relative to **RRF retrieval order** after the same hard-filtered candidate pool.

Phase 10.6 **evaluates** the fixed baseline configuration. It does **not** tune weights.

## Benchmark

| Field | Value |
|-------|--------|
| Name | `productiq_lexical_retrieval_v1` |
| Version | `1.0.0` |
| File | `resources/evaluation/lexical_retrieval_benchmark_v1.json` |
| Queries | 10 |
| Judged relevant IDs | 44 (binary, manual) |
| K values | 1, 5, 10, 20, 50 |

Labels come from existing lexical benchmark judgments only. No synthetic labels. No labels derived from BM25/vector/RRF ranks.

## Evaluation population

For each benchmark query:

1. `ProductionRetrievalPipeline.retrieve_ranked_evaluation_bundle` runs **one** retrieval + filter + baseline ranking pass.
2. **RRF metrics** use product IDs in **filtered-pool RRF order**, truncated to `evaluation_top_k` (default 50).
3. **Baseline metrics** use product IDs from **`RankingResponse.ranked_candidates`**, truncated to the same `evaluation_top_k`.

Both systems see the **same filtered candidate pool**; only ordering differs.

| Setting | Role |
|---------|------|
| `candidate_pool_top_k` | RRF fusion depth (must match pipeline config) |
| `evaluation_top_k` | Ordered list depth for metric computation (default 50) |

## Metrics

Reuses Phase 4.8 / 4.18 implementations in `productiq.retrieval.evaluation.metrics` and `evaluate_single_query`:

- MRR (macro mean of per-query reciprocal rank)
- Precision@K and Recall@K for K ∈ {1, 5, 10, 20, 50}
- Macro averaging across benchmark queries (existing convention)

nDCG is not implemented in ProductIQ evaluation today; binary labels only.

## Candidate coverage

Diagnostic per query:

```
coverage = |judged relevant ∩ filtered pool| / |judged relevant|
```

Distinguishes **relevant never retrieved/filtered in** from **relevant present but ranked low** in the evaluated top list.

## Diagnostics

| Tag | Meaning |
|-----|---------|
| `RELEVANT_NOT_IN_CANDIDATE_POOL` | Judged relevant ID absent from filtered pool |
| `RELEVANT_RETRIEVED_BUT_RANKED_LOW` | Relevant in pool but absent from baseline evaluated top-K |
| `RELEVANT_RANKED_HIGH` | First relevant hit at rank 1 (baseline list) |

Tags are observational; they do not assign root causes to features.

## RRF vs baseline comparison

`RankingEvaluationComparison` exposes, per metric/K:

- `rrf` — aggregate metric on RRF-ordered list
- `baseline` — aggregate metric on baseline-ordered list
- `delta` — `baseline - rrf` (positive ⇒ baseline higher)

No winner fields, recommendations, or automatic selection.

## Version metadata

`RankingBenchmarkEvaluationResult.lineage` records:

- `evaluation_version` (`10.6.0`)
- benchmark name/version
- `evaluation_top_k`, `candidate_pool_top_k`, `k_values`
- `ranking_version`, `feature_schema_version`, `normalization_schema_version`, `ranking_pipeline_version` from live pipeline run when available

## Code map

| Module | Role |
|--------|------|
| `ranking/evaluation/evaluator.py` | `RankingBenchmarkEvaluator` |
| `ranking/evaluation/schema.py` | Contracts |
| `ranking/evaluation/diagnostics.py` | Failure-analysis tags |
| `ranking/evaluation/coverage.py` | Pool coverage |
| `ranking/evaluation/comparison.py` | Metric triples |
| `retrieval/production_pipeline.py` | `retrieve_ranked_evaluation_bundle` |

## Non-goals

Weight tuning, hyperparameter search, LTR training, retrieval/RRF/filtering changes, production optimization, Phase 10.7+.

## Notebook

`notebooks/data_engineering/43_ranking_evaluation.ipynb`
