# Phase 12.9 — Search Statistical / Significance Analysis

**Status:** Paired query-level inference over persisted Phase 12 evaluation artifacts  
**Benchmark:** `productiq_search_benchmark_v1` v1.0.0

## Purpose

Phase **12.9** summarizes uncertainty and contrast for **paired query-level metrics** already computed in Phase **12.3** and stored in Phase **12.5** / **12.7** artifacts. It does **not** rerun retrieval, ranking, or metric computation, and it does **not** select a winner, recommended variant, or promotion decision.

```text
Phase 12.5 / 12.7 artifacts (per_query metrics)
        ↓
Align queries by query_id
        ↓
Paired differences d_i = c_i - r_i
        ↓
Bootstrap CI + sign-flip permutation p-value
        ↓
Persisted statistical artifact
```

## Paired design

For each metric and K (when applicable):

- Reference value `r_i` and candidate value `c_i` come from `SearchQueryMetricResult` rows with the same `query_id`.
- Paired difference: `d_i = c_i - r_i`.
- Observed effect: `mean(d_i) = candidate_mean - reference_mean`.

Aggregate-only comparisons without query pairing are not used.

## Bootstrap method

- **Unit:** eligible paired differences `(d_1, …, d_N)`.
- **Resampling:** draw `N` indices with replacement (`random.Random(seed)` per configuration).
- **Statistic:** mean of resampled differences.
- **CI:** **percentile method** at `(α/2)` and `(1 - α/2)` for configured `confidence_level` (default 0.95).
- **Defaults:** `n_bootstrap_samples=5000`, `random_seed=42`.

## Permutation test

- **Null:** mean paired difference is zero (descriptive randomization test, not a causal claim).
- For each permutation, independently flip the sign of each `d_i` with probability 0.5.
- Test statistic: `|mean(d')|`.
- **Two-sided Monte Carlo p-value:** `(count + 1) / (n_permutations + 1)` where count is permutations with `|mean| ≥ |observed mean|`.
- **Defaults:** `n_permutations=10000`, `random_seed=42`.

## Missing / ineligible values

Phase **12.3** semantics are preserved:

- **Recall@K** may be `None` when no judged-relevant products exist at `min_relevant_grade` (`recall_aggregate_eligible=False`).
- **nDCG@K** may be `None` when not computable.
- `None` is never coerced to zero for inference.

Each comparison records `total_queries`, `eligible_queries`, `excluded_queries`, and `exclusion_reasons`. Bootstrap and permutation run only when `eligible_queries > 0`.

## Query alignment

Reference and candidate `per_query` sets must have **identical** `query_id` sets. Mismatches raise `RetrievalError` (fail-fast). Pairing is by `query_id`, not list position.

## Sample size and small-sample limitation

The canonical benchmark has **10** queries. Each comparison sets `sample_size = eligible_queries` and, when below `small_sample_query_threshold` (default 30), attaches an explicit `small_sample_warning` stating that results are conditional on the curated benchmark and must not be generalized to production traffic.

## Multiple-comparison configuration

`multiple_testing_method` defaults to **`none`** (raw p-values reported). When set to **`benjamini_hochberg`**, adjusted p-values are stored in `adjusted_p_value` using a transparent step-up procedure over all comparisons in the run. Raw p-values are always retained. Many metric/K tests are reported; raw p-values should not be read as definitive without considering the comparison family.

## Deterministic RNG

Bootstrap and permutation each use an explicit `random.Random(random_seed)` instance. Identical artifacts, configuration, and seeds produce identical CIs and p-values. No timestamps appear in deterministic artifact identity.

## Effect semantics

Primary effect: `observed_delta = candidate_mean - reference_mean`. Optional `mean_absolute_paired_difference` is descriptive only. No standardized effect sizes are introduced beyond existing metric scales.

## Artifact

- File: `resources/evaluation/productiq_search_statistical_analysis_v1.json`
- Schema: **12.9.0**
- Deterministic SHA-256 checksum (excludes checksum field and runtime-only metadata)

## API

```python
from pathlib import Path
from productiq.retrieval.evaluation.search_evaluation.statistical_runner import (
    run_default_search_statistical_analysis,
    run_search_statistical_analysis,
)

run_default_search_statistical_analysis(Path("."))
```

## Why this is not a deployment recommendation

Statistical outputs are **evidentiary** inputs for human review and later reporting (Phase 12.10). The contract explicitly excludes winner, best, recommended, promotion, and production decision fields.

## Relationship to other phases

| Phase | Role |
|-------|------|
| 12.3 | Metric definitions |
| 12.5 / 12.7 | Persisted per-query metrics |
| 12.6 | Descriptive aggregate deltas |
| 12.8 | Failure / depth diagnostics |
| **12.9** | Paired bootstrap + permutation |
| 12.10 | Reporting |
