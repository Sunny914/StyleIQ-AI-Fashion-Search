# Phase 12.1 — Search Evaluation Contract

**Status:** Contract / architecture (Phase 12.2 benchmark artifact; Phase 12.3+ runners)  
**Scope:** Search evaluation domain only — independent from search implementation and from recommendation evaluation

## Purpose

Define typed, immutable contracts for reproducible **search** quality measurement:

```text
Benchmark + relevance judgments
        ↓
SearchEvaluationRequest
        ↓
Evaluation runner (Phase 12.3+)
        ↓
SearchEvaluationVariant → ranked product IDs
        ↓
Shared metric primitives (P/R/HitRate/MRR/nDCG)
        ↓
SearchVariantEvaluationResult
        ↓
SearchExperimentComparison (deltas only)
```

Phase 12.1 does **not** implement the experiment runner or call BM25/semantic/RRF/LTR directly.

## Search vs recommendation evaluation

| Domain | Input | Output |
|--------|-------|--------|
| **Search** | `query_text` + query judgments | Ranked products for the query |
| **Recommendation** | `seed_product_id` + seed judgments | Recommended products for the seed |

Both may reuse generic metric functions (`productiq.retrieval.evaluation.metrics`, recommendation `hit_rate_at_k` / `ndcg_at_k` in Phase 12.2+), but **contracts remain separate** (`search_evaluation` vs `recommendation.evaluation`).

Legacy Phase 4.8 binary lexical benchmarks remain valid; `lexical_query_to_search_evaluation_query` maps binary relevant IDs to graded judgments (default grade **2**).

## Benchmark

- **`SearchEvaluationBenchmark`** — metadata + `queries`
- **`SearchEvaluationBenchmarkMetadata`** — name, version, catalog artifact, checksum, methodology, limitations
- Unique `query_id` values required; at least one query

## Query

**`SearchEvaluationQuery`**: `query_id`, `query_text`, `query_category`, `relevance_judgments`

Judgments are **curated** — not BM25, vector, RRF, ranking, or LTR scores.

## Relevance judgments

**`SearchRelevanceJudgment`**: `product_id`, `grade` in **0–3**

| Grade | Meaning (documentation convention) |
|-------|-------------------------------------|
| 0 | Irrelevant |
| 1 | Weakly relevant |
| 2 | Relevant |
| 3 | Highly relevant |

Duplicate `(query_id, product_id)` within a query is **rejected** at validation time.

## Metrics

**`SearchMetricConfiguration`**:

- `k_values` (defaults to `DEFAULT_EVALUATION_K_VALUES`)
- `evaluation_top_k`
- `min_relevant_grade` (default **2** for P/R/HitRate/MRR)
- `compute_ndcg` flag for graded nDCG in Phase 12.2+

Supported families (documented): Precision@K, Recall@K, HitRate@K, MRR, nDCG@K. Implementations reuse existing modules in later phases — not reimplemented in 12.1.

## Macro aggregation

**`SearchQueryMetricResult`** — query-level metrics  
**`SearchAggregateMetricResult`** — macro means over queries  

Judgments are **not** pooled across queries.

## Evaluation variants

**`SearchEvaluationVariant`**: `variant_name`, `variant_version`, optional `description`, `lineage_labels`

The evaluation framework consumes **`SearchRankedResultsForQuery`** (`query_id`, `ranked_product_ids`) and does not branch on retrieval algorithms inside metric code.

## Results

**`SearchVariantEvaluationResult`**: `lineage`, `per_query`, `aggregate`

**`SearchEvaluationLineage`**: evaluation version, benchmark identity, variant identity, metric configuration, catalog/checksum fields — **no timestamps in deterministic identity**

## Comparisons

**`SearchExperimentComparison`**: absolute deltas for aggregate metrics only.

No `winner`, `best_variant`, or recommended variant fields.

## Determinism

Same benchmark + variant identity + metric configuration + catalog state → stable serialized result identity (JSON dumps used in tests).

## Validation summary

- Positive unique `k_values`
- Valid `min_relevant_grade`
- Unique benchmark `query_id`s
- Non-empty judgments; unique `product_id` per query
- Valid variant identity strings
- `extra="forbid"` on contracts

## Explicit non-goals (Phase 12.1)

- No new retrieval or ranking algorithms
- No LTR training/inference
- No online A/B traffic routing
- No FastAPI or production serving endpoints
- No statistical significance testing
- No complete experiment runner (Phase 12.3+)

## Phase 12.2 benchmark artifact

Canonical graded benchmark, loader, integrity validation, and legacy lexical adapter: see **`docs/architecture/search-benchmark-artifact.md`**.

## Phase 12.3 metrics

Precision@K, Recall@K, HitRate@K, MRR, and nDCG@K computation (no runner): see **`docs/architecture/search-evaluation-metrics.md`**.

## Phase 12.4 runner

Generic variant execution + metric orchestration: see **`docs/architecture/search-evaluation-runner.md`**.

## Phase 12.5 baseline evaluation

Real BM25/semantic/RRF baselines on `productiq_search_benchmark_v1`: see **`docs/architecture/search-baseline-evaluation.md`**.

## Phase 12.6 experiment framework

Group baseline artifacts, validate a shared evaluation envelope, and report descriptive aggregate deltas vs a reference variant: see **`docs/architecture/search-experiment-framework.md`**.

## Phase 12.7 ranking experimentation

Hold retrieval candidates fixed and compare ranking variants (retrieval order, baseline ranker, LTR): see **`docs/architecture/search-ranking-experimentation.md`**.

## Phase 12.8 failure analysis

Classify observed retrieval/ranking outcomes for judged products from persisted 12.5/12.7 artifacts (no execution): see **`docs/architecture/search-failure-analysis.md`**.

## Phase 12.9 statistical analysis

Paired bootstrap and permutation summaries over persisted per-query metrics: see **`docs/architecture/search-statistical-analysis.md`**.

## Phase 12.10 unified reporting

Single offline report synthesizing Phase 12.5–12.9 artifacts: see **`docs/architecture/search-evaluation-reporting.md`**.

## Phase 12.11 evaluation hardening

Artifact integrity, cross-artifact invariants, provenance, determinism, and fail-closed validation: see **`docs/architecture/search-evaluation-hardening.md`**.

## Related legacy modules

Phase 4.8 lexical evaluation, Phase 4.18 unified retrieval evaluation, and Phase 11.7 recommendation evaluation remain unchanged. Phase 12.1 adds the **`search_evaluation`** package as the forward-looking search experimentation contract.
