# Phase 10.9 — Ranking Hardening & Failure Analysis

**Status:** Implemented (final Phase 10 sub-phase)  
**Production ranking:** Phase **10.4** deterministic baseline via `retrieve_ranked()`

## Phase 10 ranking architecture

```text
Query → Retrieval → Hard Filtering → RankingCandidate
  → Feature Extraction → Normalization → 10.4 Baseline → Top-K → RankingResponse
```

Offline LTR (10.7 artifact + 10.8 inference) is a **parallel path** on normalized features only.

## Production ranking boundary

- `ProductionRankingStageConfig.enabled=True` (default) runs the **10.4 baseline** in `retrieve_ranked()`.
- `experimental_ltr.enabled` defaults to **False** and is **not** wired into `retrieve_ranked()`.
- Enabling experimental LTR without an artifact path fails validation at config construction.
- `load_experimental_ltr_artifact()` is for **explicit offline** use only.

**10.4 remains the production ranking baseline.**

**10.7/10.8 LTR remains offline/experimental unless future work explicitly integrates it.**

## Ranking invariants (10.9)

Central helpers in `ranking/invariants.py`:

| Check | Function |
|-------|----------|
| Unique candidate IDs | `validate_unique_ranking_product_ids` |
| Unique feature IDs | `validate_unique_normalized_feature_product_ids` |
| Candidate/feature alignment | `validate_candidate_feature_product_alignment` |
| Positive top_k | `validate_positive_top_k` |
| Response ranks/scores | `validate_ranking_response_invariants` |
| Deterministic tie-break | `deterministic_ranking_sort_key` → `(-score, product_id)` |

Baseline and LTR rankers call `validate_ranking_response_invariants` before returning.

## Failure categories

Structured records (`RankingFailureCategory`) include:

- Relevant not in candidate pool (reuses 10.6 diagnostics)
- Relevant retrieved but ranked low
- Empty candidate pool
- Evaluation depth limits
- LTR artifact incompatibility (offline)
- Additional categories for alignment/context/ties (extensible schema)

Each record separates **`observed_facts`** from **`diagnosis_hypotheses`** (explicitly not proven root causes).

## Diagnostic methodology

1. Run Phase **10.6** benchmark evaluation (`RankingBenchmarkEvaluator`).
2. Map `RankingQueryDiagnostics` tags to failure records (`build_ranking_failure_records`).
3. Emit JSON report (`ranking_failure_analysis_v10_9.json` convention).

## Failure analysis report

See `docs/architecture/ranking-failure-analysis-report.md` for the documented category template.

## Operational characteristics

`operational_measurements_from_timings()` captures when available:

- candidate pool size, top_k, returned counts
- `RankedSearchTimingsMs` breakdown (retrieval / features / normalization / ranking)
- LTR inference latency: **not yet measured** in production path

Labels: `benchmark/test measurement`, `implementation property`, or `not yet measured`.

## LTR safety boundary

- Incompatible artifacts raise `RankingError` via `validate_ltr_artifact_for_pipeline`.
- No silent fallback to baseline inside LTR inference.
- Production pipeline does not invoke LTR.

## Known limitations

- 10-query / 44-judgment lexical benchmark only
- Incomplete ground truth
- Failure hypotheses are not causal proof

## Production-readiness considerations

- Invariants are enforced in rankers and test suite
- Production path remains baseline-only with explicit experimental LTR config guardrails
- No hyperparameter tuning or LTR superiority claims in this phase

## Code map

| Module | Role |
|--------|------|
| `ranking/invariants.py` | Shared invariant validation |
| `ranking/hardening/` | Version + production safety |
| `ranking/failure_analysis/` | Structured diagnostics + report |
| `retrieval/production_ranking_config.py` | `experimental_ltr` opt-in block |

## Notebook

`notebooks/data_engineering/46_ranking_hardening_and_failure_analysis.ipynb`

## Version

`RANKING_HARDENING_VERSION` / `RANKING_FAILURE_ANALYSIS_VERSION` = **10.9.0**
