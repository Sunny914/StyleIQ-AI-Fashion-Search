# Phase 12.8 — Search Retrieval & Ranking Failure Analysis

**Status:** Diagnostic layer over persisted Phase 12.5 / 12.7 artifacts  
**Benchmark:** `productiq_search_benchmark_v1` v1.0.0

## Purpose

Phase **12.8** classifies **observed** evaluation outcomes for judged-relevant products. It does **not** execute retrieval, ranking, metrics aggregation for experiments, significance testing, or reporting dashboards.

```text
Phase 12.5 baseline artifacts (BM25, semantic, RRF)
        +
Optional Phase 12.7 ranking experiment artifact
        ↓
Failure analysis (12.8) — per product / query / variant / K
        ↓
Persisted diagnostic artifact + aggregates
```

## Observation vs causal inference

Each `SearchFailureAnalysisRecord` states **where** a relevant product appeared in an artifact-ranked list (or that it was absent from the evaluated depth). The layer must **not** assert unproven causes (embedding ambiguity, stemming, ranker misunderstanding, LTR feature failure) unless future work adds direct structured evidence.

## Failure taxonomy

| Category | Evidence required |
|----------|-------------------|
| `RANKED_IN_TOP_K` | Known 1-based rank ≤ `analysis_k` within artifact depth |
| `RETRIEVED_BELOW_K` | Known rank > `analysis_k` and rank ≤ `depth_limited_threshold` (default 10) |
| `DEPTH_LIMITED` | Known rank > `depth_limited_threshold` and rank ≤ `evaluated_depth` |
| `ABSENT_FROM_EVALUATED_DEPTH` | Product not present in artifact ranked list (no rank invented) |
| `NOT_RETRIEVED` | Reserved in taxonomy; absent cases use `ABSENT_FROM_EVALUATED_DEPTH` when only top-N lists exist |
| `JUDGED_RELEVANT_BUT_CONSTRAINT_INCOMPATIBLE` | Structured query constraints + product filtering metadata disagree (see constraints) |

**Depth semantics:** If an artifact only stores top 50 IDs, diagnostics may say the product is **absent from evaluated top 50**. They may **not** claim rank 87 unless rank 87 appears in the source artifact.

## Retrieval failure analysis

For BM25 and semantic baseline artifacts, cross-method **retrieval-set relationships** use Phase **4.18**-compatible labels:

- `BM25_ONLY`
- `SEMANTIC_ONLY`
- `RETRIEVED_BY_BOTH`
- `NOT_RETRIEVED_BY_EITHER`

Counts apply to judged-relevant products at the minimum shared evaluated depth between BM25 and semantic slices. No inference when separate retrieval provenance is unavailable.

## Ranking failure analysis

When `productiq_search_ranking_experiment_v1.json` is present:

- Each ranking variant slice is analyzed like a baseline ranked list.
- **Reference ranks** come from the experiment reference variant (default: `retrieval_order`).
- For non-reference ranking variants, `rank_delta = candidate_rank - reference_rank` when both ranks are known.
- Deltas are **descriptive** only (no “improvement” / “degradation” labels in 12.8).

Missing reference or candidate rank → `rank_delta` is `None` (explicit observation string).

## Constraint diagnostics

`JUDGED_RELEVANT_BUT_CONSTRAINT_INCOMPATIBLE` is emitted only when:

1. `enable_constraint_diagnostics=True` in analysis configuration, **and**
2. Active query constraints are parsed from benchmark query text via `build_query_representation`, **and**
3. Catalog `FilteringRepresentation` for the product fails `filtering_satisfies_query_constraints`.

Default runs keep `enable_constraint_diagnostics=False` because benchmark queries rarely encode hard filters in text alone. Never infer constraint mismatch from free-form product text.

## Aggregation

Deterministic aggregates by:

- `variant_name`, `analysis_k`, `failure_category`
- Optional breakdown dimensions: `query_id`, `relevance_grade`

Plus retrieval relationship aggregates (`pattern`, `product_count`).

## Deterministic artifact

- File: `resources/evaluation/productiq_search_failure_analysis_v1.json`
- Schema: **12.8.0**
- Checksum: SHA-256 over JSON body excluding `deterministic_checksum_sha256` and runtime-only fields (same helper as 12.5 baselines)
- No timestamps in deterministic identity

## API

```python
from pathlib import Path
from productiq.retrieval.evaluation.search_evaluation.failure_analysis_runner import (
    run_default_search_failure_analysis,
    run_search_failure_analysis,
)

run_default_search_failure_analysis(Path("."))
# or analyze without writing:
result = run_search_failure_analysis(Path("."))
```

## Relationship to other Phase 12 work

| Phase | Responsibility |
|-------|----------------|
| 12.3 | Metrics |
| 12.4 / 12.5 | Run retrieval baselines |
| 12.6 | Experiment envelope + descriptive deltas |
| 12.7 | Fixed-pool ranking experiment |
| **12.8** | Failure / depth / retrieval-pattern diagnostics |
| 12.9 | Statistical significance |
| **12.10** | Unified reporting |

## Limitations

- Diagnostics are bounded by artifact ranked-list depth.
- Constraint and retrieval-pattern sections require the corresponding source artifacts and configuration flags.
- Re-running 12.8 with the same inputs reproduces the same checksum; changing 12.5/12.7 inputs changes diagnostics accordingly.
