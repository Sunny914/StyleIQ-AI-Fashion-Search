# Phase 4.17 — Retrieval Failure Analysis

**Status:** Implemented  
**Implements:** Deterministic diagnostic analysis over existing Phase 4.8 / 4.14 / 4.16 benchmark artifacts  
**Does not implement:** Retrieval fixes, reranking, filtering, Phase 4.18+

## Purpose

Explain **where** retrieval succeeds or weakens for the curated 10-query benchmark and **judged relevant** products only. Observed ranks and scores are separated from interpretive diagnostic labels.

## Inputs (read-only)

| Artifact | Role |
|----------|------|
| `lexical_retrieval_benchmark_v1.json` | Queries, categories, judged relevant IDs |
| `lexical_retrieval_benchmark_v1_run.json` | Full-catalog BM25 ranks (official Phase 4.8) |
| `semantic_retrieval_benchmark_v1_run.json` | Lineage |
| `semantic_retrieval_benchmark_v1_analysis.jsonl` | Semantic ranks + native similarities |
| `hybrid_rrf_benchmark_v1_run.json` | BM25, semantic, and **live scoped** RRF ranked lists |
| `product_representations.parquet` | Representation evidence for review candidates |

No embeddings, vector indexes, or BM25 indexes are rebuilt during analysis.

## Outputs

| File | Content |
|------|---------|
| `retrieval_failure_analysis_v1.json` | Full report + lineage |
| `retrieval_failure_analysis_v1.jsonl` | One diagnostic record per query × judged product |
| `retrieval_failure_summary_v1.json` | Aggregates by pattern and query category |

```bash
python scripts/run_retrieval_failure_analysis.py
```

## Diagnostic model

Each record covers one **judged relevant** product:

- **Observed:** BM25 / semantic / RRF retrieval, 1-based ranks, depths @1/@5/@10/@20/@50, native vector similarity when recorded
- **BM25 native score:** null (Phase 4.8 run stores IDs only)
- **RRF fusion score:** recomputed from source ranks and `rank_constant=60` (same formula as Phase 4.16)
- **Patterns:** `RETRIEVED_BY_BOTH`, `BM25_ONLY`, `SEMANTIC_ONLY`, `NOT_RETRIEVED_BY_EITHER`, `RETRIEVED_BUT_RRF_LOW_RANK`, `DEPTH_LIMITED`
- **Interpretive diagnostics:** explicitly labeled hypotheses, not root causes
- **Representation evidence:** attached when `representation_review_candidate` is true

Products not in the judged set are **not** labeled irrelevant; analysis does not score unjudged catalog items.

## Limitations

- Incomplete ground truth (benchmark `limitations` text).
- RRF lists reflect **scoped BM25** live fusion; BM25 comparison lists in the hybrid artifact are full-catalog Phase 4.8 runs.
- Unjudged catalog products may also be relevant.

## Code

- `src/productiq/retrieval/evaluation/failure_analysis_schema.py`
- `src/productiq/retrieval/evaluation/failure_analyzer.py`
- `src/productiq/retrieval/evaluation/failure_reporting.py`
- `tests/retrieval/test_retrieval_failure_analysis.py`

## Notebook

`notebooks/data_engineering/33_retrieval_failure_analysis.ipynb` (also `34_retrieval_failure_analysis.ipynb`)

## Scope boundary

**Out of scope:** fixing retrieval, re-running live benchmarks, cross-encoder reranking, **Phase 4.18**.
