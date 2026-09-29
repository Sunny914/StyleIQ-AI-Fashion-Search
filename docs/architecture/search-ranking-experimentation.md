# Phase 12.7 — Search Ranking Experimentation

**Status:** Fixed-candidate ranking comparisons (Phase 12.8+ failure analysis, 12.9 significance)  
**Benchmark:** `productiq_search_benchmark_v1` v1.0.0

## Motivation

Phase 12.5–12.6 measure **end-to-end search** (retrieval + implicit order). Phase **12.7** isolates **ranking** by holding the **candidate set fixed** per query and re-ordering with Phase 10 rankers.

```text
Benchmark queries
        ↓
Fixed candidate pool (one retrieval provenance, e.g. RRF 12.5 baseline)
        ↓
Ranking variant A / B / C  (same candidates)
        ↓
Phase 12.3 metrics + Phase 12.1 comparisons
```

## Fixed candidate-set methodology

- One `SearchRankingCandidatePool` lists, per `query_id`, `candidate_product_ids` (unique, deterministic order).
- Optional full `RetrievalCandidate` rows are required for baseline/LTR feature extraction.
- All ranking variants in an experiment **must** consume the same pool; mismatches raise `RetrievalError` (no union/intersection).

Default pool source: **`productiq_search_benchmark_v1_baseline_rrf_run.json`** ranked IDs (Phase 12.5). When only IDs are persisted, retrieval scores are **reconstructed** in retrieval order for ranking features (documented in artifact `provenance_notes`).

## Ranking variants

| Type | Implementation |
|------|----------------|
| `retrieval_order` | Preserve candidate pool order (reference default) |
| `baseline_ranker` | Phase 10.4 `rank_candidates` |
| `ltr` | Phase 10.8 `rank_candidates_with_ltr` (requires artifact) |

No production ranking changes; no LTR promotion.

## Phase 10 reuse

Thin adapters in `ranking_variant_executor.py` call existing:

- `extract_features_for_request` / `normalize_features_for_query`
- `rank_candidates` / `rank_candidates_with_ltr`
- `RankingProductContextProvider` (parquet-backed for default runs)

## Retrieval provenance

`SearchRetrievalProvenanceRecord` records which retrieval variant generated the pool (`retrieval_variant_name`, `retrieval_variant_version`). Different retrieval → different experiment configuration.

## Metrics and comparison

Reuses Phase **12.3** (`run_search_evaluation`) and Phase **12.1** `compare_search_evaluation_variants` (candidate − reference). No winner, significance, or optimization.

## Artifacts

- File: `resources/evaluation/productiq_search_ranking_experiment_v1.json`
- Schema: **12.7.0**, deterministic checksum (excludes runtime metadata)
- LTR variant included when any of these resolve: `PRODUCTIQ_EXPERIMENTAL_LTR_ARTIFACT_DIR`, `resources/processed/experimental_ltr_ranker/`, or Phase 10.7 reference `resources/models/ranking_ltr_reference_v10_7_0/` (train via notebook `44_learning_to_rank.ipynb` or `train_ltr_model`)

## Relationship to Phase 12.6

12.6 groups **full variant evaluation artifacts** (retrieval baselines). 12.7 groups **ranking variants** under one **fixed pool**. Both use the same comparison contract; neither selects a winner.

## Phase 12.9

Statistical significance belongs to 12.9; 12.7 outputs descriptive deltas only.

## API

```python
from pathlib import Path
from productiq.retrieval.evaluation.search_evaluation.ranking_experiment_runner import (
    run_default_search_ranking_experiment,
)

run_default_search_ranking_experiment(Path("."))
```

## Limitations

- ID-only pools reconstruct retrieval metadata for features (not identical to live RRF candidate objects).
- LTR requires an explicit offline artifact path; no fabricated LTR scores.
- Default parquet context load requires catalog rows for all candidate IDs.
