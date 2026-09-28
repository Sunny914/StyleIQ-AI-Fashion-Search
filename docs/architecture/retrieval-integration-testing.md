# Phase 4.20 — Retrieval Integration Testing

**Status:** Implemented  
**Scope:** Opt-in end-to-end validation of the production retrieval path against live ProductIQ infrastructure  
**Does not implement:** New retrieval algorithms, benchmark regeneration, Phase 5

## Integration boundary

| Mode | Behavior |
|------|----------|
| Default `pytest` | Integration tests **skipped** (no PostgreSQL, BM25, or BGE required) |
| Opt-in | Requires explicit environment flags (see below) |

Integration tests live under `tests/retrieval/integration/` and are marked `integration`.

## Required environment

```powershell
$env:PRODUCTIQ_RUN_INTEGRATION_TESTS = "1"
$env:PRODUCTIQ_PRODUCTION_RETRIEVAL_SMOKE = "1"
pytest tests/retrieval/integration/ -q
```

Additional conventions reused from earlier phases:

- `PRODUCTIQ_RUN_INTEGRATION_TESTS=1` — PostgreSQL / pgvector (see `tests/database/test_integration.py`)
- Phase-specific smoke flags (RRF, hybrid, semantic) remain separate from Phase 4.20

Application settings load from the existing ProductIQ `.env` / `get_settings()` path (database URL, credentials).

## Required artifacts (read-only)

| Artifact | Path |
|----------|------|
| BM25 index | `resources/processed/bm25_lexical_index.pkl` |
| Embeddings (reference) | `resources/processed/product_embeddings.parquet` |
| Representations (BM25 fallback) | `resources/processed/product_representations.parquet` |
| Lexical benchmark (scoped BM25 fallback) | `resources/evaluation/lexical_retrieval_benchmark_v1.json` |

PostgreSQL must contain the ProductIQ `products` table with `embedding vector(384)` and HNSW index (Phase 4.12). Expected full-catalog contract: **367,172** rows when fully loaded.

No artifact or index rebuild is performed in this phase.

## Real dependency graph

Session-scoped fixture `live_production_retrieval` constructs once per integration session:

```text
create_bm25_retriever_from_index_path (or scoped fallback)
create_bge_small_en_v15_encoder
create_semantic_retriever_from_engine → pgvector HNSW
create_rrf_hybrid_retriever
PostgresCatalogCandidateFilter
ProductionRetrievalPipeline
```

## Smoke-query matrix

Deterministic `QueryRepresentation` cases (explicit constraints where needed — no NL parsing):

1. Brand + product — `"Nike running shoes"`
2. Brand + color — `"black Nike running shoes"` + `brand_normalized`, `color`
3. Price — `"Nike running shoes under 5000"` + `max_discount_price_inr`
4. Multi-constraint — black / Nike / ≤5000 / Men
5. Semantic/descriptive — `"comfortable shoes for running"`
6. Impossible brand constraint — expect zero results
7. Empty lexical + semantic intent — expect zero results (separate test)

## Integration invariants

Reusable helpers: `tests/retrieval/integration/invariants.py`

- Unique candidate IDs
- Finite scores
- Catalog ID existence
- top_k bounds
- Production metadata coherence
- RRF fusion ordering
- Provenance / fusion score integrity
- Hard constraints via `filtering_satisfies_query_constraints`
- Deterministic repeated execution (candidate-level fields)

## Hard-filter validation

Returned candidates for constrained queries are validated with the same **`FilteringRepresentation`** / **`filtering_satisfies_query_constraints`** semantics as production filtering. Imperfect recall does not fail tests; any returned row must satisfy active hard constraints.

## Determinism

Repeated identical `RetrievalRequest` against unchanged catalog/infrastructure must yield identical candidate IDs, order, scores, and provenance. Metadata timestamps are not compared.

## Benchmark artifacts

Phase 4.8 / 4.14 / 4.16 / 4.17 / 4.18 evaluation JSON artifacts are **not** modified or regenerated. Live smoke results are not scored against historical benchmark metrics.

## Known limitations

- Scoped BM25 fallback (memory) may be used if the full pickle cannot load; full-chain test still exercises real RRF, semantic, pgvector, filter, and pipeline.
- Restrictive filters plus fixed `candidate_pool_top_k=50` may yield zero results legitimately.
- Per-stage latency baselines were **not** added (would require pipeline instrumentation beyond this phase).

## Manual smoke script

```bash
set PRODUCTIQ_RUN_INTEGRATION_TESTS=1
python scripts/run_production_retrieval_smoke.py "Nike running shoes"
```

## Notebook

`notebooks/data_engineering/37_retrieval_integration_testing.ipynb`

## Completion

Phase 4.20 completes the **retrieval subsystem** integration validation. Phase 5 (API / product surface) is out of scope.
