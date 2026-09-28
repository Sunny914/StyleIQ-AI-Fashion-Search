# Phase 4.19 — Production Retrieval Pipeline

**Status:** Implemented  
**Implements:** Single production retrieval entry point orchestrating RRF over-retrieval, structured hard filtering, and final top-k trim  
**Does not implement:** Final ranking (Phase 4.20), query parsing, embedding/index rebuild, degraded partial retrieval

## Responsibility

`ProductionRetrievalPipeline` is the service-layer entry point for ProductIQ retrieval after query understanding has produced a `QueryRepresentation`.

```text
QueryRepresentation
        ↓
ProductionRetrievalPipeline.retrieve(RetrievalRequest)
        ↓
RRF hybrid retrieval (depth = candidate_pool_top_k)
        ↓
structured hard constraints (candidate-ID catalog lookup)
        ↓
deterministic trim to request.top_k
        ↓
RetrievalResponse
```

The pipeline **orchestrates** validated Phase 4.8–4.16 components. It does not reimplement BM25, vector search, embeddings, or RRF.

## Candidate over-retrieval

| Setting | Meaning |
|---------|---------|
| `RetrievalRequest.top_k` | Final number of candidates returned to callers |
| `ProductionRetrievalConfig.candidate_pool_top_k` | RRF retrieval depth before filtering |

Validation: `candidate_pool_top_k >= request.top_k`.

Hard filtering can remove fused candidates. Retrieving only `request.top_k` before filtering would shrink effective recall under restrictive constraints.

## Structured hard filtering

- Uses existing `QueryRepresentation.constraints` (no re-parsing, no LLM).
- Evaluated deterministically against canonical catalog fields via `FilteringRepresentation`.
- `CatalogCandidateFilter.filter_candidate_ids` loads **only** candidate product IDs (PostgreSQL `IN` query in production).
- Preserves **RRF order**; filtering never re-sorts by catalog attributes.
- Unsupported or unevaluable hard constraints should fail explicitly (`CatalogValidationError`), not silently pass.

Filtering is **not** performed by embeddings or BM25 scores. Retrieval scores remain diagnostic through the pipeline.

## Dependency injection

Inject at construction time:

- `Retriever` (typically `RRFHybridRetriever` over injected BM25 + semantic retrievers)
- `CatalogCandidateFilter` (`PostgresCatalogCandidateFilter` or test doubles)
- `ProductionRetrievalConfig`

`retrieve()` must not load BM25 indexes, embedding models, vector indexes, or database engines.

Application startup (see `production_factory.create_production_retrieval_pipeline_from_retrievers`):

```text
load BM25 index → BM25 retriever
init BGE encoder + DB → semantic retriever
compose RRF retriever
open DB session → Postgres catalog filter
construct ProductionRetrievalPipeline
```

## Empty results

| Condition | Behavior |
|-----------|----------|
| No usable lexical or semantic intent | Empty `RetrievalResponse`; RRF not invoked |
| RRF returns no candidates | Empty response with fused-stage metadata when available |
| All candidates fail hard constraints | Empty response; metadata includes `filtered_candidate_count=0` |

Zero-result search is not an exception.

## Failures

BM25, semantic, RRF, and catalog filter failures propagate using the existing exception hierarchy. No silent fallback or partial degradation in this phase.

## Observability

`RetrievalResponseMetadata` is extended with:

- `candidate_pool_top_k`
- `filtered_candidate_count`
- `returned_candidate_count`
- `production_pipeline_version`

RRF-stage fields (`lexical_candidate_count`, `overlap_count`, `rrf_rank_constant`, etc.) are preserved from the fused response when present. Execution metadata must not contain product catalog attributes.

## Retrieval vs ranking

Phase 4.19 output is still **retrieval**: native BM25/vector scores and `fusion_score` are unchanged by filtering. There is no final learning-to-rank or cross-encoder step (Phase 4.20+).

## Known limitation

Recall under heavy filtering depends on `candidate_pool_top_k`. If the pool is too shallow, valid products ranked below the pool cutoff never reach the filter stage.

## Code map

| Module | Role |
|--------|------|
| `production_pipeline.py` | Orchestration |
| `production_config.py` | Pool depth configuration |
| `production_factory.py` | Startup wiring helper |
| `catalog_candidate_filter.py` | Candidate-ID hard filter |
| `catalog_constraint_match.py` | Constraint satisfaction rules |

## Notebook

`notebooks/data_engineering/36_production_retrieval_pipeline.ipynb`

## Out of scope

Phase 4.20 final ranking, HTTP API layer, evaluation artifact changes, index/embedding rebuilds.
