# Phase 11.7 — Recommendation Evaluation

**Status:** Implemented  
**Scope:** Offline measurement only (does not change recommendation behavior)

ProductIQ has **no user-behavior dataset** (no clicks, purchases, sessions, or impressions). Metrics use **curated offline graded judgments**, not behavioral ground truth.

## Evaluation purpose

Reproducibly measure recommendation pipeline outputs on benchmark seeds for:

- Relevance (P@K, R@K, HitRate@K, MRR, nDCG@K)
- Coverage (catalog / brand / product-type diagnostics)
- Diversity ratios on outputs
- Constraint / shortfall diagnostics
- Per-seed failure observations

Evaluation does **not** tune Phase 11.5 weights.

## Benchmark

- **Name:** `productiq_recommendation_v1`
- **Version:** `1.0.0`
- **Artifact:** `resources/evaluation/productiq_recommendation_v1.json`
- **Seeds:** 20 real catalog product IDs (shared review batches with lexical benchmark v1)

## Labeling methodology

Graded relevance **0–3** assigned during manual offline catalog review:

| Grade | Meaning |
|-------|---------|
| 3 | Highly relevant substitute/alternative for the seed |
| 2 | Relevant |
| 1 | Somewhat relevant |
| 0 | Not relevant (typically omitted from judgment lists) |

Labels are **not** derived from semantic similarity, BM25, candidate scores, baseline ranker output, or selection results.

## Metric definitions

### Precision@K

`relevant_in_top_k / min(K, returned_count)`; **0.0** when nothing is returned.

**Relevant** for P/R/HitRate/MRR: judgments with grade ≥ `min_relevant_grade` (default **2**).

### Recall@K

`relevant_in_top_k / |judged relevant|`; **None** per-query when judged relevant set is empty (macro aggregate skips undefined seeds).

Recall is **not** full-catalog recall.

### HitRate@K

Per seed: **1** if any judged-relevant item appears in top-K, else **0**. Macro mean across seeds.

### MRR

Reciprocal rank of the first judged-relevant item in the evaluated list; **0** when none appear.

### nDCG@K

Graded gains from the 0–3 scale; **None** when ideal DCG is zero.

## Coverage

- **Recommendation catalog coverage:** `unique recommended product IDs / eligible_catalog_product_count` (metadata denominator)
- **Candidate pool coverage:** `|judged relevant ∩ candidate pool| / |judged relevant|`

## Diversity diagnostics

- `unique_brand_ratio` / `unique_product_type_ratio` on returned lists when context metadata is supplied
- Reported separately from relevance (more diversity ≠ automatically better)

## Constraint metrics

Seed leakage flag, duplicate recommendation count, max-per-brand / max-per-product-type violation counts (when selection config + context provided).

## Shortfall

`shortfall_count = max(requested_top_k - returned_count, 0)`  
`shortfall_rate = shortfall_count / requested_top_k`

Shortfall is a **system/constraint diagnostic**, not automatic quality failure.

## Variants compared

| Variant | Output evaluated |
|---------|------------------|
| `baseline_ranker_11_5` | Phase 11.5 ranked list |
| `baseline_ranker_11_5_plus_selection_11_6` | Phase 11.6 final list |

Same benchmark, same evaluation config, **fixed** 11.5 weights.

## Per-seed results

`RecommendationSeedMetrics` stores per-seed relevance, diversity, constraint, shortfall, and `failure_observations`.

## Failure observations

Diagnostic tags such as `NO_RELEVANT_RETRIEVED`, `INSUFFICIENT_CANDIDATES`, `RELEVANT_DROPPED_BY_CONSTRAINT`, `SHORTFALL` — observations, not proven root causes.

## Reproducibility

`RecommendationEvaluationLineage` records benchmark version, evaluation version `11.7.0`, ranker/selection versions, K values, and catalog artifact checksum when present. Deterministic evaluation (no randomness).

## Result artifact

`RecommendationBenchmarkEvaluationResult` is JSON-serializable via `evaluation_result_to_dict` for machine-readable runs (e.g. future `productiq_recommendation_v1_run.json`).

## Known limitations

- Small curated benchmark
- Incomplete judgment set vs full catalog
- No behavioral validation
- Diversity/context metrics require optional selection context metadata at evaluation time

## Explicit non-goals

No LTR training, weight tuning, MMR, personalization, popularity models, or automatic “winner” selection.
