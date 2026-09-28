# Phase 10.4 — Deterministic Baseline Ranker

**Status:** Implemented  
**Scope:** Post-retrieval weighted ranking over Phase 10.3 normalized features (no LTR, no pipeline integration)

## Purpose

Provide a transparent, reproducible **reference baseline** that ranks retrieval candidates after feature extraction (10.2) and query-group normalization (10.3). Weights are explicit configuration, not learned or tuned against metrics in this phase.

## Architecture position

```
retrieval → RankingCandidate
         → extract_features (10.2)
         → normalize_feature_rows (10.3)
         → rank_candidates (10.4)
         → RankingResponse
```

RRF and hybrid fusion remain in retrieval. The baseline ranker **re-ranks** the provided candidate set; it does not replace RRF.

## Inputs and outputs

| Input | Contract |
|-------|----------|
| Candidates | `RankingRequest.candidates` (`RankingCandidate`) |
| Features | `NormalizedRankingFeatures` per `product_id` (10.3 output) |
| Config | `BaselineRankingConfig` (10.4) |

| Output | Contract |
|--------|----------|
| Ranked list | `RankingResponse` / `RankedCandidate` (10.1) |

API: `rank_candidates(request=..., normalized_features_by_product_id=..., baseline_config=...)`.

Identity checks: every candidate must have matching `product_id` on its feature row; duplicate IDs are rejected.

## Feature inclusion and weights

Scoring uses **normalized** values only (no re-normalization, no raw INR in the ranker).

Default reference weights (`BaselineFeatureWeights`, version `10.4.0`):

| Feature | Weight | Notes |
|---------|--------|-------|
| `retrieval.rrf_score` | 0.18 | Hybrid fusion signal (normalized) |
| `retrieval.bm25_score` | 0.12 | |
| `retrieval.vector_similarity` | 0.12 | |
| `retrieval.bm25_rank` | 0.08 | Uses 10.3 rank normalization |
| `retrieval.vector_rank` | 0.08 | |
| `retrieval.retrieved_by_both` | 0.03 | Provenance bonus |
| `matching.brand_match` | 0.10 | Binary 0/1 normalized |
| `matching.attribute_overlap` | 0.07 | |
| `matching.color_match` | 0.06 | |
| `matching.product_type_match` | 0.05 | |
| `matching.category_gender_match` | 0.04 | |
| `matching.matched_attribute_count` | 0.04 | |
| `matching.material_match` | 0.03 | |
| `retrieval.retrieved_by_bm25` | 0.00 | **Excluded** (redundant with scores) |
| `retrieval.retrieved_by_vector` | 0.00 | **Excluded** |
| `matching.constraint_match` | 0.00 | **Excluded** (diagnostic) |
| `catalog.*` | 0.00 | **Excluded** (no price-preference assumption) |

Weights are **not optimal**; they exist for interpretability and future LTR comparison.

## Scoring formula

For each included feature *i* with normalized value `v_i` (or missing):

```
contribution_i = weight_i * (v_i if v_i is not None else missing_value_contribution)
ranking_score = sum(contribution_i)
```

`compute_baseline_score` returns a `BaselineScoreBreakdown` with per-feature contributions for debugging.

## Missing-value policy

Phase 10.3: `None ≠ 0`. When `v_i is None`, the ranker does **not** impute a feature value. It adds `weight_i * missing_value_contribution` (default **`0.0`**). Missing features therefore contribute zero by default but remain semantically missing in `NormalizedRankingFeatures`.

## Deterministic ordering

Sort key (10.1): `(-ranking_score, product_id)`. Equal scores tie-break lexicographically on `product_id`. Ranks are assigned 1..n contiguously before `apply_ranking_top_k`.

## Top-k

Returns at most `RankingRequest.top_k` rows via `apply_ranking_top_k`. Does not change retrieval `candidate_pool_top_k`.

## Response metadata

`RankingResponse.config.ranking_version` is set to `BaselineRankingConfig.baseline_version` (`10.4.0`). Tie-break uses `RankingConfig.tie_break_key` (`product_id`).

## Finite scores

Non-finite normalized inputs are rejected at schema validation or scoring. Output `ranking_score` must be finite.

## Non-goals (Phase 10.4)

- ML / LTR / learned weights / training / model persistence  
- Ranking evaluation or weight tuning  
- Production pipeline wiring (10.5+)  
- Retrieval, filtering, or RRF changes  

## Future LTR

The baseline provides a fixed interpretable line for comparing learned rankers in later phases. Dataset rows from 10.3 supply features and labels separately.

## Code map

- `baseline_config.py` — `BaselineRankingConfig`, `BaselineFeatureWeights`
- `baseline_scoring.py` — weighted sum + breakdown
- `baseline_ranker.py` — `rank_candidates`
