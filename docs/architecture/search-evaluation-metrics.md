# Phase 12.3 — Search Evaluation Metrics

**Status:** Metric computation layer (Phase 12.4 implements the evaluation runner)  
**Contracts:** Phase 12.1 results; Phase 12.2 benchmark judgments

## Role in the stack

```text
SearchEvaluationBenchmark + SearchRankedResultsForQuery
        ↓
compute_search_query_metrics / evaluate_search_variant_metrics  (12.3)
        ↓
SearchQueryMetricResult + SearchAggregateMetricResult
        ↓
Evaluation runner (12.4) — executes search, supplies ranked IDs
```

Phase 12.3 does **not** call BM25, vector search, RRF, ranking, or LTR. It only consumes ranked product IDs and curated judgments.

## Metric definitions

All metrics use the ranked prefix **`ranked_product_ids[:evaluation_top_k]`** (after duplicate/empty validation). For each configured **`k` in k_values`**, retrieval primitives evaluate the first **`k`** positions of that prefix (same semantics as Phase 4.8 / 11.7).

| Metric | Definition |
|--------|------------|
| **Precision@K** | Relevant items in top‑K ÷ `min(K, len(prefix))`; **0.0** when prefix is empty |
| **Recall@K** | Relevant in top‑K ÷ total judged relevant (grade ≥ threshold); **`None`** when no judged relevant products |
| **HitRate@K** | **1.0** if any relevant in top‑K, else **0.0**; **0.0** when no judged relevant products |
| **MRR** | Reciprocal rank of first relevant item in the evaluation prefix; **0.0** if none |
| **nDCG@K** | DCG@K ÷ IDCG@K using **graded** gains; **0.0** when prefix empty; **`None`** when ideal DCG is zero |

## Binary vs graded relevance

- **Precision, Recall, HitRate, MRR:** binary relevance — judgment counts as relevant when **`grade >= min_relevant_grade`** (default **2**). Grades **2** and **3** are relevant for the Phase 12.2 benchmark.
- **nDCG@K:** uses **actual grades** (0–3). Unjudged products in the ranked list contribute gain **0**. Grades are **not** collapsed to binary for nDCG.

Controlled by **`SearchMetricConfiguration`**: `k_values`, `evaluation_top_k`, `min_relevant_grade`, `compute_ndcg`.

## Macro aggregation

1. Compute **`SearchQueryMetricResult`** per benchmark query (stable order: sorted by `query_id`).
2. **Macro mean** over queries for Precision@K, HitRate@K, and MRR (all queries included).
3. **Recall@K:** macro mean over queries with **`recall_aggregate_eligible=True`** only; if none, mean **0.0**. **`recall_aggregate_query_count`** records eligible queries.
4. **nDCG@K:** when `compute_ndcg=True`, macro mean over queries where nDCG is defined (non‑`None`); **`ndcg_aggregate_query_count`** uses the minimum per‑K sample count (same pattern as recommendation evaluation). When `compute_ndcg=False`, per‑query `ndcg_at_k` is empty and aggregate nDCG means are **0.0**.

No micro‑averaging across judgments.

## Ranked result validation

- Empty or whitespace **`product_id`** in rankings → error.
- **Duplicate** ranked IDs → error (Pydantic on **`SearchRankedResultsForQuery`** and **`validate_search_ranked_product_ids`**). No silent deduplication in the search metric layer.

Legacy Phase 4.8 **`normalize_retrieved_product_ids`** still deduplicates inside shared primitives; search inputs are validated **before** calling those helpers so duplicates never change scores silently.

## Shared primitives (reuse)

| Primitive | Source |
|-----------|--------|
| `precision_at_k`, `recall_at_k`, `reciprocal_rank`, `macro_mean`, `mean_reciprocal_rank` | `productiq.retrieval.evaluation.metrics` (Phase 4.8) |
| `judged_relevant_product_ids`, `hit_rate_at_k`, `ndcg_at_k` | `productiq.recommendation.evaluation.metrics` (Phase 11.7) |

Legacy lexical and recommendation evaluators are unchanged; search metrics compose the same formulas via these modules.

## Edge-case summary

| Case | Behavior |
|------|----------|
| Empty ranking | P@K=0, R@K=0 or None, Hit=0, MRR=0, nDCG=0 |
| No judged relevant (binary) | R@K=None, `recall_aggregate_eligible=False`, Hit=0 |
| K > len(prefix) | Denominator uses actual prefix length (precision) |
| `evaluation_top_k` < len(ranking) | Metrics use truncated prefix only |
| Invalid grades | `RetrievalError` from `validate_search_relevance_grades` |
| Missing/extra ranked queries in variant eval | `RetrievalError` |

## API (12.3)

- **`compute_search_query_metrics`**
- **`aggregate_search_query_metrics`**
- **`evaluate_search_variant_metrics`** — builds **`SearchVariantEvaluationResult`** with lineage from benchmark + variant

## Related docs

- `docs/architecture/search-evaluation-contract.md` — Phase 12.1
- `docs/architecture/search-benchmark-artifact.md` — Phase 12.2
