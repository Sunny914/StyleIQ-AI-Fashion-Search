# Phase 12.11 — Search Evaluation Hardening

**Status:** Final Phase 12 engineering sub-phase (validation only)  
**Package:** `src/productiq/retrieval/evaluation/search_evaluation/hardening/`

## Purpose

Phase **12.11** hardens the existing Phase 12 evaluation graph against corrupted, stale, incompatible, or malformed artifacts and against accidental fallback or evaluative semantics. It does **not** add retrieval, ranking, metrics, statistics, or recommendations.

Relationship to **12.10:** Reporting assembles the canonical report; hardening validates upstream artifacts and cross-artifact contracts before and during that assembly. Determinism checks extend 12.10 reproducibility with repeated regeneration (minimum five runs in audit).

## Artifact integrity

For each persisted artifact on the evaluation path:

- File existence and readable UTF-8 JSON
- Expected `artifact_schema_version`
- Domain validators (baseline, ranking, failure, statistical, report)
- Declared `deterministic_checksum_sha256` when present (fail closed on mismatch)

No silent repair or checksum rewriting.

## Cross-artifact invariants

- Benchmark **query_id** set must match each baseline per-query set exactly (no missing, extra, or duplicate IDs)
- Shared **metric_configuration** across baselines (via 12.10 envelope validation plus execution/evaluation top-K checks)
- Canonical **12.9 comparison pairs** only:
  - BM25 → Semantic
  - BM25 → RRF
  - retrieval_order → baseline_ranker
  - retrieval_order → LTR  
  Rejects redundant **RRF → BM25** reverse pairs

## Benchmark compatibility

Benchmark name/version alignment is enforced in 12.10 `validate_report_sources`; hardening adds query-set and duplicate-query checks on loaded sources.

## Metric compatibility

`validate_metric_configuration_identity` rejects any drift in `k_values`, `execution_top_k`, `evaluation_top_k`, `min_relevant_grade`, or `compute_ndcg` without normalization.

## Provenance validation

Catalog artifact and `source_representation_checksum` must match across 12.5 baselines and optional 12.6/12.7 envelopes. Variant `(name, version)` pairs must be unique among baselines.

## Determinism

`validate_report_generation_determinism` regenerates the report multiple times (default 5) and requires identical JSON body, checksum, and Markdown. Persisted Markdown under `resources/evaluation/reports/` must match regeneration when present.

## Failure handling

Explicit `RetrievalError` messages for missing files, invalid JSON, unsupported schema versions, checksum mismatch, benchmark/query/metric/provenance mismatch, and malformed 12.8/12.9 payloads. **LTR** absence is recorded as a limitation (`ltr_artifact_status`); hardening does not substitute another model.

## Evaluation safety

Forbidden evaluative field names (`winner`, `best`, `recommended`, etc.) remain blocked by 12.10 report validation. Hardening audit confirms report safety and that metrics/statistics in the report match source artifacts (copy-only semantics).

## Known limitations (preserved)

- BM25 may use `benchmark_scoped_slice_4912_docs` (not full catalog)
- LTR depends on gitignored `resources/models/ranking_ltr_reference_v10_7_0/`
- Statistical pairs are directional only (no reverse RRF→BM25)

## API

```python
from pathlib import Path
from productiq.retrieval.evaluation.search_evaluation.hardening import (
    run_search_evaluation_hardening_audit,
)

run_search_evaluation_hardening_audit(Path("."), include_determinism=True, determinism_repetitions=5)
```

Report construction calls `validate_search_evaluation_hardening_sources` after `validate_report_sources` in `report_builder`.

## Layout

- `integrity.py` — load and validate individual artifacts
- `invariants.py` — benchmark, metric depth, statistical pair invariants
- `provenance.py` — catalog/representation and variant identity
- `determinism.py` — repeated report regeneration stability
- `failure_modes.py` — LTR status and forbidden fallback patterns
- `validation.py` — audit orchestration

## Notebook

`notebooks/data_engineering/65_search_evaluation_hardening.ipynb` demonstrates integrity, invariants, provenance, determinism, and audit status on canonical artifacts.
