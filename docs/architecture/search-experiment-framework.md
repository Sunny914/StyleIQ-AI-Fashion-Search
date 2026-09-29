# Phase 12.6 — Search Experiment / Variant Framework

**Status:** Experiment grouping and descriptive comparisons (Phase 12.7+ ranking experiments, 12.9 significance)  
**Benchmark:** `productiq_search_benchmark_v1` v1.0.0 (unchanged)

## Baseline run vs experiment

| Concept | Meaning |
|---------|---------|
| **Baseline run (12.5)** | One persisted `SearchVariantEvaluationResult` for a single search variant on the benchmark. |
| **Experiment (12.6)** | A named grouping of two or more baseline-compatible evaluation artifacts under one **shared evaluation envelope**, plus **descriptive aggregate metric deltas** versus an explicitly designated **reference variant**. |

Phase 12.6 **does not** execute retrieval. It **loads** Phase 12.5 (or compatible) artifacts, validates envelope compatibility, and reuses Phase 12.1 `compare_search_evaluation_variants` for deltas.

```text
Phase 12.5 baseline JSON (per variant)
        ↓
SearchEvaluationExperimentDefinition (artifact references + reference variant)
        ↓
validate_shared_evaluation_envelope
        ↓
compare_search_evaluation_variants (reference → each candidate)
        ↓
SearchEvaluationExperimentResult (+ optional persisted experiment JSON)
```

## Experiment identity

`SearchEvaluationExperimentDefinition` carries:

- `experiment_name`, `experiment_version`, `description`
- `reference_variant_name` — exactly one numerical reference (not “best” or “correct”)
- `variant_artifacts` — `SearchBaselineArtifactReference` rows (unique `variant_name`)

Persisted experiment artifacts use `artifact_schema_version` **12.6.0** and include both the definition and `SearchEvaluationExperimentResult`.

Default baseline comparison experiment:

- Name: `productiq_search_benchmark_v1_baseline_comparison`
- Version: **1.0.0**
- File: `resources/evaluation/productiq_search_benchmark_v1_baseline_comparison_experiment_v1.json`

## Reference variant semantics

- Must appear in `variant_artifacts` (validated at definition construction).
- Used only as the left-hand side of aggregate deltas: **delta = candidate − reference**.
- Maps to `SearchExperimentComparison.baseline_variant` (12.1 naming: baseline = reference).
- No winner, recommendation, or rank ordering is produced.

## Common evaluation envelope

`validate_shared_evaluation_envelope` requires identical lineage fields across all loaded results:

- `benchmark_name`, `benchmark_version`
- full `metric_configuration` (including `k_values`, `evaluation_top_k`, `execution_top_k`, `min_relevant_grade`, `compute_ndcg`)
- `catalog_artifact`, `source_representation_checksum`

Mismatch raises `RetrievalError` (fail-fast; no silent pooling of incompatible runs).

## Artifact references

`SearchBaselineArtifactReference` stores:

- `variant_name`, `variant_version`
- `artifact_path` (repo-relative when possible)
- optional `deterministic_checksum_sha256` (validated when loading)
- optional `retrieval_index_mode` (e.g. BM25 scope note from 12.5 provenance)

The experiment result **references** baseline artifacts; it does not duplicate full 12.5 bodies.

## Absolute delta semantics

For each non-reference variant, one `SearchExperimentComparison` reports:

- `precision_at_k_delta`, `recall_at_k_delta`, `hit_rate_at_k_delta`, `ndcg_at_k_delta`, `mrr_delta`

All are **candidate aggregate minus reference aggregate**. Query-level `None` values in per-query metrics remain in source artifacts; aggregate comparisons use macro means from 12.3.

## Why no winner / recommendation

Product selection and deployment decisions belong to later phases (12.9 significance, 12.10 reporting). This layer only groups compatible measurements and reports numeric deltas with explicit lineage.

## Relationship to Phase 12.4 runner

If new variant results are needed, run **12.4** via **12.5** (`run_search_baseline_evaluation.py`) first. Phase 12.6 consumes those artifacts; it does not implement a second query loop.

## Relationship to Phase 12.9 significance analysis

12.6 output is an input **envelope** for significance testing. No p-values, confidence intervals, or “significant improvement” labels appear here.

## BM25 scoped baseline qualification

The checked-in BM25 baseline may record `retrieval_provenance.index_mode` = `benchmark_scoped_slice_4912_docs` when the full persisted index path is not used. Experiments copy that note into `provenance_notes` so comparisons are not misread as full-catalog BM25 runs.

## API entry points

- `run_search_evaluation_experiment(definition, repo_root)`
- `build_default_baseline_comparison_experiment_definition(repo_root)`
- `run_default_baseline_comparison_experiment(repo_root)` — writes the default experiment JSON under `resources/evaluation/`
