# Lexical retrieval evaluation benchmark

## Purpose

Measure **retrieval quality** for ProductIQ lexical search (BM25 today; vector/hybrid later) using a small, **manually curated** query set. This is not a claim about production traffic or full-catalog relevance.

## Artifact

- **`lexical_retrieval_benchmark_v1.json`** — version `1.0.0`, 10 queries, binary `relevant_product_ids`
- Catalog context: `resources/processed/product_representations.parquet` (checksum recorded in the JSON when present)

## Methodology

1. Pick realistic query strings (brand, color, material, gender/category, multi-attribute).
2. Inspect catalog / `lexical_text` rows for candidate products.
3. Label products as **relevant** when lexical and attribute alignment is defensible for the query.
4. Do **not** label every possible relevant SKU in ~367k products.

## Limitations

- **Incomplete ground truth** — recall metrics are relative to judged IDs only.
- **Small sample** — suitable for portfolio transparency, not statistical generalization.
- **Binary relevance** — no graded 0–3 labels in v1 (evaluation contracts allow future extension).

## Metrics (see architecture doc)

Macro-averaged Precision@K, Recall@K, and MRR across benchmark queries. See `docs/architecture/search-retrieval-contract.md` Phase 4.8.

## Running evaluation

```python
from pathlib import Path

from productiq.retrieval import create_bm25_retriever_from_index_path
from productiq.retrieval.evaluation import (
    LexicalRetrievalEvaluator,
    load_lexical_retrieval_benchmark,
)

benchmark = load_lexical_retrieval_benchmark(
    Path("resources/evaluation/lexical_retrieval_benchmark_v1.json")
)
retriever = create_bm25_retriever_from_index_path(
    Path("resources/processed/bm25_lexical_index.pkl")
)
evaluator = LexicalRetrievalEvaluator(retrieval_top_k=50)
result = evaluator.evaluate(benchmark, retriever)
print(result.aggregate)
```

Optional pytest smoke: `PRODUCTIQ_LEXICAL_EVAL_SMOKE=1 pytest tests/retrieval/test_evaluation_evaluator.py -k integration`

If loading the full persisted index fails with `MemoryError`, the runner and integration test fall back to a **benchmark-scoped** in-memory index (judged relevant IDs plus a capped sample per query term). Metrics from that slice are real BM25 scores but are **not** identical to full-catalog retrieval; prefer the persisted index when RAM allows.

Run: `python scripts/run_lexical_retrieval_benchmark.py`

---

## Semantic retrieval benchmark (Phase 4.14)

### Purpose

Measure **semantic candidate retrieval quality** for ProductIQ using the same manually curated relevance judgments as the lexical benchmark (comparable P@K / R@K / MRR), evaluated through **`SemanticRetriever`** (not raw pgvector).

### Artifacts

- **`semantic_retrieval_benchmark_v1.json`** — version `1.0.0`, 10 queries, shared `relevant_product_ids` with lexical v1, embedding/index lineage fields
- **`semantic_retrieval_benchmark_v1_run.json`** — aggregate + per-query metrics, retrieval lineage, incomplete-judgment warning
- **`semantic_retrieval_benchmark_v1_analysis.jsonl`** — per-query retrieved IDs and cosine similarity scores

### Relevance policy

Binary labels: a product is relevant only when inspectable catalog fields support the query’s explicit intent. Labels are independent of embedding similarity, BM25, LLM output, or retriever rankings.

### Limitations

Incomplete ground truth (same as lexical v1). Recall is relative to judged IDs only.

### Running evaluation

```bash
python scripts/run_semantic_retrieval_benchmark.py
```

Optional pytest: `PRODUCTIQ_RUN_INTEGRATION_TESTS=1` and `PRODUCTIQ_SEMANTIC_RETRIEVAL_SMOKE=1` on `tests/retrieval/test_semantic_retrieval_evaluation.py`

See `docs/architecture/search-retrieval-contract.md` Phase 4.14.

---

## RRF candidate fusion benchmark (Phase 4.16)

Evaluates **RRFHybridRetriever** on the same 10-query judgments (P@K, R@K, MRR) and records BM25 vs semantic vs RRF aggregates in one run artifact.

```bash
python scripts/run_rrf_retrieval_benchmark.py
```

- **`hybrid_rrf_benchmark_v1_run.json`**
- **`hybrid_rrf_benchmark_v1_analysis.jsonl`** (per-query first relevant ranks)

Does not modify lexical or semantic benchmark run files.
