# Phase 12.10 — Search Evaluation Reporting & Reproducibility

**Status:** Read-only synthesis of Phase 12.5–12.9 artifacts  
**Canonical JSON:** `resources/evaluation/productiq_search_evaluation_report_v1.json`  
**Canonical Markdown:** `resources/evaluation/reports/productiq_search_evaluation_report_v1.md`

## Purpose

Phase **12.10** assembles a **single evaluation report** and **reproducibility manifest** from persisted Phase 12 outputs. It does not rerun retrieval, ranking, metrics (12.3), failure classification (12.8), or statistical tests (12.9).

```text
12.5 Baseline results
        ↓
12.6 Variant experiments
        ↓
12.7 Ranking experiments
        ↓
12.8 Failure diagnostics
        ↓
12.9 Statistical analysis
        ↓
12.10 Evaluation reporting & reproducibility
```

## Report sections

1. **Metadata** — report identity and evaluation contract version  
2. **Benchmark reference** — name, version, artifact path (not full judgments)  
3. **Configuration** — metric configuration, execution/evaluation top-K  
4. **Variant summaries** — macro metrics copied from 12.5 / 12.7 aggregates  
5. **Pairwise comparisons** — reference/candidate values and absolute deltas from 12.6 / 12.7  
6. **Failure analysis summary** — aggregates and retrieval patterns from 12.8  
7. **Statistical analysis summary** — paired effects, CIs, p-values from 12.9  
8. **Reproducibility manifest** — artifact checksums, schema versions, seeds, index modes  
9. **Limitations** — scoped BM25, LTR artifact availability, small-sample caveats  

## Reproducibility limitations (preserved explicitly)

- **BM25 / RRF:** Phase 12.5 BM25 may use `benchmark_scoped_slice_4912_docs` (not full-catalog BM25). RRF may inherit that provenance.  
- **LTR:** Ranking experiment LTR depends on `resources/models/ranking_ltr_reference_v10_7_0/` (gitignored); fresh clones may need retraining or explicit artifact configuration.  
- **Statistics:** 12.9 canonical pairs are directional only (no redundant RRF→BM25 reverse pair).

## Non-goals

No winner, best, recommended, preferred, promote, promotion, or deployment decision fields.

## API

```python
from pathlib import Path
from productiq.retrieval.evaluation.search_evaluation.reporting import (
    run_default_search_evaluation_report,
)

run_default_search_evaluation_report(Path("."))
```

## Package layout

`src/productiq/retrieval/evaluation/search_evaluation/reporting/`

- `report_schema.py` — contracts  
- `report_loader.py` — artifact loaders  
- `report_validation.py` — compatibility checks  
- `report_builder.py` — deterministic assembly  
- `reproducibility.py` — manifest builder  
- `report_artifact.py` — JSON persistence + checksum  
- `report_renderer.py` — Markdown from JSON report  

## Determinism

Same upstream artifacts → identical report JSON and checksum. No timestamps in deterministic identity.
