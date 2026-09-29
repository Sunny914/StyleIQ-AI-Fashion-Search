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

---

## Recommendation evaluation benchmark (Phase 11.7)

### Purpose

Offline **recommendation** quality measurement on seed products (not search queries). Uses curated graded judgments; **not** user clicks or purchases.

### Artifact

- **`productiq_recommendation_v1.json`** — version `1.0.0`, **20** seed cases, graded relevance **0–3**
- Catalog context: `resources/processed/product_representations.parquet` (checksum in JSON metadata)

### Labeling policy

Judgments come from the same manual offline catalog review batches as lexical v1. Labels are **not** derived from BM25, embeddings, candidate scores, baseline ranker, or selection output.

### Limitations

Small curated sample; recall is relative to judged IDs only; no behavioral ground truth.

See `docs/architecture/recommendation-evaluation.md`.

---

## Search evaluation benchmark (Phase 12.2)

### Purpose

Offline **search** quality measurement on curated queries (not recommendation seeds). Uses graded judgments **0–3**; Phase 12.3+ runners consume the same artifact.

### Artifact

- **`productiq_search_benchmark_v1.json`** — artifact schema `12.2.0`, benchmark version `1.0.0`, **10** queries, **44** judgments (grade **2**, derived from lexical v1 binary labels)
- Catalog context: `resources/processed/product_representations.parquet` (checksum in metadata)

### Legacy source

Judgments align with **`lexical_retrieval_benchmark_v1.json`** (`productiq_lexical_retrieval_v1`). Use `convert_lexical_benchmark_path_to_search` for explicit adaptation; legacy 4.8 evaluation behavior is unchanged.

See `docs/architecture/search-benchmark-artifact.md`.

```bash
python scripts/run_search_baseline_evaluation.py --variants bm25
```

---

## Search baseline runs (Phase 12.5)

Persisted variant evaluations under `resources/evaluation/`:

- `productiq_search_benchmark_v1_baseline_bm25_run.json`
- `productiq_search_benchmark_v1_baseline_semantic_run.json`
- `productiq_search_benchmark_v1_baseline_rrf_run.json`

See `docs/architecture/search-baseline-evaluation.md`.

---

## Search experiment comparison (Phase 12.6)

Groups the Phase 12.5 baseline artifacts under one evaluation envelope and reports **descriptive metric deltas** vs an explicit **reference variant** (default: BM25). No winner or significance testing.

- **`productiq_search_benchmark_v1_baseline_comparison_experiment_v1.json`** — experiment definition + `SearchEvaluationExperimentResult`

```python
from pathlib import Path

from productiq.retrieval.evaluation.search_evaluation import run_default_baseline_comparison_experiment

run_default_baseline_comparison_experiment(Path("."))
```

See `docs/architecture/search-experiment-framework.md`.

---

## Search ranking experiment (Phase 12.7)

Fixed **RRF candidate pool**; compare retrieval order vs Phase 10 baseline ranker vs experimental LTR. LTR loads from `PRODUCTIQ_EXPERIMENTAL_LTR_ARTIFACT_DIR`, `resources/processed/experimental_ltr_ranker/`, or trained reference `resources/models/ranking_ltr_reference_v10_7_0/` (see Phase 10.7 notebook).

- **`productiq_search_ranking_experiment_v1.json`**

```python
from pathlib import Path
from productiq.retrieval.evaluation.search_evaluation.ranking_experiment_runner import (
    run_default_search_ranking_experiment,
)

run_default_search_ranking_experiment(Path("."))
```

See `docs/architecture/search-ranking-experimentation.md`.

---

## Search failure analysis (Phase 12.8)

Deterministic diagnostics over Phase 12.5 baseline runs and optional Phase 12.7 ranking experiment (observed ranks and retrieval patterns only; no causal claims).

- **`productiq_search_failure_analysis_v1.json`**

```python
from pathlib import Path
from productiq.retrieval.evaluation.search_evaluation.failure_analysis_runner import (
    run_default_search_failure_analysis,
)

run_default_search_failure_analysis(Path("."))
```

See `docs/architecture/search-failure-analysis.md`.

---

## Search statistical analysis (Phase 12.9)

Paired query-level bootstrap confidence intervals and sign-flip permutation p-values over Phase 12.5 / 12.7 per-query metrics (no retrieval, ranking, or metric recomputation; no winner/promotion fields).

- **`productiq_search_statistical_analysis_v1.json`**

```python
from pathlib import Path
from productiq.retrieval.evaluation.search_evaluation.statistical_runner import (
    run_default_search_statistical_analysis,
)

run_default_search_statistical_analysis(Path("."))
```

See `docs/architecture/search-statistical-analysis.md`.

---

## Search evaluation report (Phase 12.10)

Read-only synthesis of Phase 12.5–12.9 artifacts with reproducibility manifest and deterministic Markdown render.

- **`productiq_search_evaluation_report_v1.json`**
- **`reports/productiq_search_evaluation_report_v1.md`**

```python
from pathlib import Path
from productiq.retrieval.evaluation.search_evaluation.reporting import (
    run_default_search_evaluation_report,
)

run_default_search_evaluation_report(Path("."))
```

See `docs/architecture/search-evaluation-reporting.md`.

---

## Search evaluation hardening (Phase 12.11)

Fail-closed integrity, cross-artifact invariants, provenance checks, and determinism audit over canonical Phase 12 artifacts.

```python
from pathlib import Path
from productiq.retrieval.evaluation.search_evaluation.hardening import (
    run_search_evaluation_hardening_audit,
)

run_search_evaluation_hardening_audit(Path("."), include_determinism=True, determinism_repetitions=5)
```

See `docs/architecture/search-evaluation-hardening.md`.

