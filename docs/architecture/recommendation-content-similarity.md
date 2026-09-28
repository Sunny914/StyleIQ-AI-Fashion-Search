# Phase 11.3 — Content-Based Similarity Engine

**Status:** Implemented  
**Scope:** Seed↔candidate similarity signals only (no recommendation ranking)

Phase 11.3 computes similarity signals. It does not produce final recommendation ranking.

## Relationship to Phase 11.2

Phase 11.2 produces `RecommendationCandidate` rows with `candidate_generation_score` and multi-source provenance. Phase 11.3 consumes those candidates (plus resolved `ProductRepresentation` context) and emits `ContentSimilarity` per candidate. Generation scores are never reinterpreted as semantic or lexical similarity.

## Similarity vs candidate generation

| Concept | Phase | Meaning |
|---------|-------|---------|
| `candidate_generation_score` | 11.2 | How strongly a generator retrieved the candidate |
| `semantic_similarity` | 11.3 | Cosine similarity of catalog embeddings (seed vs candidate) |
| `lexical_similarity` | 11.3 | BM25 score of seed lexical text against candidate document |
| Structured fields | 11.3 | Scalar / multi-value attribute overlap |

## Similarity vs ranking

No score fusion, averaging, max pooling, or weighted blends are applied. Phase 11.5+ will decide how signals contribute to recommendation ranking and LTR features (Phase 11.4).

## Architecture

```text
RecommendationCandidate[]
  + seed ProductRepresentation
  + candidate ProductRepresentation map
        ↓
ContentSimilarityEngine.compute_for_candidates
        ↓
ContentSimilarity[]  →  Phase 11.4 feature engineering
```

## Similarity contract

Immutable Pydantic models (`similarity_schema.py`):

- `ContentSimilarity` — `product_id`, optional `semantic_similarity`, optional `lexical_similarity`, nested `structured`
- `StructuredProductSimilarity` — `scalars` + `multivalue` (no aggregate score)
- Schema version `11.3.0`

## Scalar similarity

For nullable scalars (`brand`, `brand_normalized`, `category_gender`, `product_type`):

- Same normalized value → `1.0`
- Different values → `0.0`
- Missing on either side → `None` (not dissimilarity)

## Multi-value similarity

Jaccard on case-normalized sets for `color`, `pattern`, `material`, `fit`, `sleeve`, `neckline`, `product_features`, `style_attributes`:

`|A ∩ B| / |A ∪ B|`

Missing multi-values remain `None`; empty sets are not manufactured from missing data.

## Structured similarity

Component-level signals only. No hidden weighted product-type + brand + color aggregate.

## Semantic similarity

Reuses `productiq.retrieval.semantic.cosine_similarity` and catalog `products.embedding` (384-d, cosine / pgvector conventions). One batch embedding load per engine call (seed + candidates). Vectorized in-memory pairwise cosine against the seed vector.

## Lexical similarity

Seed side: `build_structured_lexical_text(seed)` as BM25 query. Candidate side: existing inverted index documents. Uses `BM25Scorer.score_lexical_query` without altering BM25 semantics. Distinct from Phase 11.2 BM25 generation scores stored on candidates.

## Missing-value semantics

Missing ≠ unknown ≠ zero ≠ different. `None` vs value → `None`; value vs different value → `0.0`; same value → `1.0`.

## Embedding access

`ProductEmbeddingProvider.load_embeddings(product_ids)` — `PostgresProductEmbeddingProvider` (single `IN` query) or `InMemoryProductEmbeddingProvider` for tests. Expected pattern: **1 batch lookup** per `compute_for_candidates` when embeddings are not preloaded.

## Batch computation

Production-oriented API: `ContentSimilarityEngine.compute_for_candidates`. Optional `compute_pairwise` for tests. `preloaded_embeddings` bypasses the provider for unit tests.

## N+1 avoidance

Do not query embeddings per candidate. Tests assert a single provider call for multi-candidate batches.

## Determinism

Stable candidate ordering in outputs matches input candidate order. Structured helpers use deterministic normalization (casefold, set logic). No randomness.

## Error handling

| Condition | Error |
|-----------|-------|
| Missing candidate `ProductRepresentation` | `RecommendationError` |
| Missing required embedding | `CatalogValidationError` |
| Invalid embedding dimension (Postgres path) | `SemanticRetrievalError` |
| Cosine undefined (dimension, non-finite, zero norm) | `SemanticRetrievalError` |
| Non-finite similarity on contract | Pydantic `ValidationError` |

Infrastructure failures are not mapped to zero similarity.

## Relationship to Phase 11.4

`ContentSimilarity` rows are factual inputs for recommendation feature engineering and later ranking. This phase does not emit ranked recommendations.

## Current limitations

- No personalization, diversity, behavioral signals, or popularity features
- Lexical similarity requires an injected `BM25Scorer` (same index as catalog lexical documents)
- No caching layer beyond provider batching
- No API surface or evaluation metrics
