# Phase 10.1 — Ranking Contract

**Status:** Implemented  
**Scope:** Typed ranking inputs/outputs only (no ranker, no feature extraction, no retrieval)

## Responsibility

The ranking layer **orders an already-valid candidate set** produced after:

```text
QueryRepresentation
  → Production Retrieval (BM25 + semantic + RRF)
  → candidate pool
  → hard constraint filtering (Phase 4.19)
  → RankingRequest
  → (Phase 10.2+) features → ranker → RankingResponse
```

Ranking **must not** retrieve, fuse, filter, or load infrastructure (PostgreSQL, pgvector, BM25, embeddings).

## Non-responsibilities

| Layer | Responsibility |
|-------|----------------|
| Retrieval | Candidate generation, RRF, retrieval scores |
| Production pipeline | Pool depth, hard filters, retrieval `top_k` trim |
| Ranking (10.1 contract) | Identity, ordering semantics, auditable ranked output |
| Phase 10.2+ | Feature extraction, baseline ranker, LTR |

## Input contract

### `RankingCandidate`

- `product_id` — stable identity (matches retrieval row)
- `retrieval` — full `RetrievalCandidate` (provenance, native scores, ranks, metadata)

### `RankingRequest`

- `query` — `QueryRepresentation` (ranking context)
- `candidates` — explicit tuple (empty allowed)
- `top_k` — positive output cap
- `config` — `RankingConfig`

Validation: **unique** `product_id` values among candidates.

Adapters (no retrieval execution):

- `ranking_candidate_from_retrieval`
- `ranking_candidates_from_retrieval_response`
- `ranking_request_from_retrieval_response`

## Output contract

### `RankedCandidate`

- `product_id`, `rank` (1-based contiguous), `ranking_score` (finite)
- `candidate` — preserved `RankingCandidate` / retrieval provenance

### `RankingResponse`

- `ranked_candidates` — ordered by ascending `rank`
- `requested_top_k`, `returned_candidate_count` (computed)
- `config` — ranking version / tie-break metadata

## Candidate identity

- Ranking may **reorder** and **truncate** to `top_k` only.
- Ranking must **not** create, duplicate, or silently drop candidates except via explicit top-k truncation in the ranker stage (Phase 10.3+).
- Empty input → empty ranked output.

## top_k semantics

For `N` input candidates and requested `K`:

```text
returned_count = min(N, K)
```

Enforced on `RankingResponse` (`returned_candidate_count <= requested_top_k`).

## Deterministic ordering

Given identical candidates, query, configuration, and features, ranking output must be deterministic.

## Tie-breaking

`RankingConfig.tie_break_key` defaults to **`product_id`**.

Sort helper: `deterministic_ranking_sort_key` → `(-ranking_score, product_id)` for stable ordering when scores tie.

## Finite scores

`RankedCandidate.ranking_score` rejects NaN and ±Infinity (Pydantic validators).

## No hidden dependencies

Ranking contracts are pure data models and helpers; they do not open DB connections or load indexes/models.

## No mutation

Input candidate tuples must not be mutated by contract construction or invariant helpers (`apply_ranking_top_k` returns a slice).

## Relationship to hard filtering

Hard constraints are enforced **before** ranking by `ProductionRetrievalPipeline` / `CatalogCandidateFilter` (Phase 4.19). Ranking assumes candidates already satisfy active hard constraints.

## Phase 10.2 — Feature engineering

`RankingCandidate.retrieval` retains scores/ranks required for downstream feature extraction. Phase 10.1 does **not** compute features.

## Future ranker (10.3+) and LTR (10.5+)

- Baseline weighted ranker will consume features and produce `RankedCandidate.ranking_score`.
- Learning-to-rank may replace the baseline without changing retrieval or filtering contracts.

## Code map

| Module | Role |
|--------|------|
| `ranking/contracts.py` | Core models |
| `ranking/config.py` | `RankingConfig` |
| `ranking/adapters.py` | Retrieval → ranking mapping |
| `ranking/invariants.py` | Identity, top-k, tie-break helpers |
| `exceptions.RankingError` | Invariant violations |

## Notebook

`notebooks/data_engineering/38_ranking_contract.ipynb`
