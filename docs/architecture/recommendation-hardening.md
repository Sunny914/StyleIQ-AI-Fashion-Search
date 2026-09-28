# Phase 11.9 — Recommendation Hardening & Failure Analysis

**Status:** Implemented  
**Scope:** Production safety, cross-stage invariants, diagnostic observations (no new recommendation intelligence)

## Purpose

Harden the existing Phase 11.2–11.8 recommendation stack and connect runtime observations to Phase 11.7 evaluation diagnostics. This phase does **not** add LTR, MMR, personalization, new generators, HTTP APIs, or fallback products.

## Cross-stage invariants

`productiq.recommendation.hardening.pipeline_invariants` validates:

| Stage | Checks |
|-------|--------|
| Candidate generation | Unique IDs, seed excluded, sorted pool, finite generation scores |
| Similarity | ID alignment, schema version, finite similarity values when present |
| Features | Alignment, schema version, ordered vector width |
| Ranking | Finite scores, contiguous ranks, seed exclusion |
| Selection | Scores unchanged, query/diversity constraints on final output |
| Pipeline response | Contract invariants + SIMILAR-only production response |

The production `RecommendationPipeline` invokes these checks after each stage.

## Production guardrails

- **`IMPLEMENTED_RECOMMENDATION_TYPES`**: production supports **`SIMILAR` only**
- **`assert_production_recommendation_request`**: rejects unsupported types and `continue_on_generator_failure=True`
- **`assert_no_experimental_recommendation_rankers`**: baseline ranker path only (no LTR in production recommendation)

Unsupported types (`PERSONALIZED`, `COMPLEMENTARY`, `ALTERNATIVE`) raise `RecommendationError` — no silent fallback to `SIMILAR`.

## Seed exclusion

Seed `product_id` must not appear in the candidate pool (post-generation) or final recommendations. Validated in candidate invariants, ranking, selection, response contract, and hardening tests.

## Duplicate protection

Union/dedup remains in Phase 11.2 `merge_recommendation_candidates`. Selection rejects duplicate ranked rows. Final response contract forbids duplicate product IDs.

## Score validity

Pydantic validators on candidates, similarity, features, and ranked rows require **finite** numeric scores when present. Invalid values are rejected — not coerced to zero.

## Determinism

Identical request + catalog + configuration yields identical serialized `RecommendationResponse` (hardening stress test uses JSON, not object identity).

## Configuration validation

Existing `RecommendationRequest` / `RecommendationConfig` models enforce positive `top_k`, `top_k <= max_top_k`, and pool bounds. Pipeline adds `candidate_pool_top_k >= request.top_k`.

## Constraint integrity

Selection tests and `validate_selection_output_constraints` verify `max_per_brand`, `max_per_product_type`, and active `QueryFilterConstraints` on **final** output. Shortfalls are valid; silent relaxation is not.

## Empty results

Valid empty `RecommendationResponse` when:

- Zero candidates after generation/filtering
- All ranked rows rejected by selection (observed as `ALL_OUTPUT_REJECTED_BY_SELECTION`)

No popularity or random fallback.

## Shortfall behavior

When fewer than `requested_top_k` rows are returned, runtime observation `SHORTFALL` is recorded in pipeline execution metadata (diagnostic, not automatic quality failure).

## Error propagation

Stage failures preserve existing exception types (`CatalogValidationError`, `SemanticRetrievalError`, `RecommendationError`, …). The pipeline does not wrap all exceptions in a generic message without chaining.

## Partial generator failure

| Mode | Behavior |
|------|----------|
| **Production pipeline** | **Fail closed** — `continue_on_generator_failure` must be `False` |
| **Offline / tests** | When `continue_on_generator_failure=True`, failures are recorded in `RecommendationCandidateGenerationResult.generator_failures` and observation `PARTIAL_CANDIDATE_GENERATION` |

Partial success cannot look identical to full generator success in production.

## Failure-analysis categories

**Runtime (`RecommendationPipelineObservation`):**

- `NO_CANDIDATES`
- `PARTIAL_CANDIDATE_GENERATION`
- `SHORTFALL`
- `ALL_OUTPUT_REJECTED_BY_SELECTION`

**Offline evaluation (Phase 11.7 `RecommendationFailureObservation`):** relevance/constraint observations for benchmark analysis. Aliases documented in `EVALUATION_OBSERVATION_ALIASES`.

Failure observations are **diagnostic classifications**, not automatically proven root causes.

## Recommendation lineage

Existing structures carry lineage without new fused scores:

- Candidate `sources` + `candidate_generation_score`
- `ContentSimilarity` per candidate
- `RecommendationFeatures` groups
- `RankedRecommendation.recommendation_score` + embedded `candidate`
- Selection diagnostics (Phase 11.6)

## Production vs experimental

Production recommendation path: 11.2 → 11.3 → 11.4 → 11.5 baseline → 11.6. No LTR, MMR, or personalization in this path.

## Limitations

- No user-behavior labels or collaborative filtering
- Small curated evaluation benchmark (11.7) — runtime observations do not measure catalog-wide quality
- `continue_on_generator_failure` is for explicit offline scenarios only, not production
