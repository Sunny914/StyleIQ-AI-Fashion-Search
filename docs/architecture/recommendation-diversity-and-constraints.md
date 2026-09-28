# Phase 11.6 — Diversity and Recommendation Constraints

**Status:** Implemented  
**Scope:** Post-ranking selection only (not relevance ranking)

Phase 11.6 selects and diversifies already-ranked recommendation candidates. It does not modify their relevance scores.

## 11.5 → 11.6 boundary

Phase 11.5 produces **`RankedRecommendation`** rows with authoritative **`recommendation_score`**. Phase 11.6 applies hard and diversity constraints via deterministic greedy selection. Scores are copied unchanged; only inclusion and final **`rank`** change.

## Hard constraints

| Reason | Behavior |
|--------|----------|
| `SEED_EXCLUDED` | Never select `seed_product_id` |
| `DUPLICATE_PRODUCT` | Second+ occurrence of same `product_id` in ranked input |
| `FILTER_CONSTRAINT` | `QueryFilterConstraints` violation (reuse `filtering_satisfies_query_constraints`) |
| `FILTER_METADATA_MISSING` | Active filters but no `FilteringRepresentation` when `strict_constraints=True` |

## Diversity constraints

| Config | Behavior |
|--------|----------|
| `max_per_brand` | Cap selected rows sharing the same normalized brand key |
| `max_per_product_type` | Cap selected rows sharing the same normalized `product_type` key |

Missing brand or product_type **does not** form a shared `"unknown"` bucket; diversity quotas **do not apply** when the key is `None`.

Category/gender diversity is **not** enabled by default.

## Greedy selection

Process ranked candidates in **existing 11.5 order**. Reject on hard/diversity violation; otherwise append and renumber ranks `1..n`. Stop when `top_k` selected.

## Score preservation

No diversity penalties. Selected rows keep the same `recommendation_score` as the input ranked row.

## Top-k and shortfall

Return at most **`top_k`** rows. If constraints leave fewer valid candidates, return the smaller set without relaxing rules.

## Missing-value behavior

Diversity keys require non-empty normalized scalars. Multiple `None` brands do not compete for the same quota.

## Configuration

**`RecommendationSelectionConfig`** (`selection_version` **11.6.0**): `strict_constraints` (default `True`), optional `max_per_brand`, optional `max_per_product_type`.

## Diagnostics

**`RecommendationSelectionResult`** exposes per-row `decision`, optional `reason`, `input_rank`, and `recommendation_score` without altering **`RankedRecommendation`**.

## Determinism

No randomness; order follows 11.5 rank order only.

## Future semantic redundancy

Pairwise semantic/lexical redundancy is **not** implemented in 11.6. Phase 11.3 component similarities remain separate; catalog-level diversity limits are the initial scope.

## Explicit non-goals

No MMR, learned diversification, LTR, personalization, popularity/behavioral signals, score fusion, or relevance recomputation.

## Limitations

- Diversity requires brand/product_type from injected filtering or `ProductRepresentation` context  
- Unprocessed ranked rows after `top_k` are omitted from diagnostics  
- No automatic category_gender caps  
