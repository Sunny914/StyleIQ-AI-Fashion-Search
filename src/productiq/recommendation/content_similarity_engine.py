"""Content-based similarity engine (Phase 11.3)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from productiq.exceptions.base import CatalogValidationError, RecommendationError
from productiq.recommendation.attribute_similarity import compute_structured_product_similarity
from productiq.recommendation.catalog_embeddings import (
    ProductEmbeddingProvider,
    merge_seed_and_candidate_embedding_ids,
)
from productiq.recommendation.contracts import (
    RecommendationCandidate,
    RecommendationCandidateSource,
)
from productiq.recommendation.lexical_similarity import compute_lexical_similarities
from productiq.recommendation.similarity_schema import ContentSimilarity
from productiq.representation.schema import ProductRepresentation
from productiq.retrieval.bm25 import BM25Scorer
from productiq.retrieval.semantic import SemanticVector, cosine_similarity


class ContentSimilarityEngine:
    """Compute seed↔candidate similarity signals for Phase 11.4 feature engineering."""

    def __init__(
        self,
        *,
        embedding_provider: ProductEmbeddingProvider,
        bm25_scorer: BM25Scorer | None = None,
    ) -> None:
        self._embedding_provider = embedding_provider
        self._bm25_scorer = bm25_scorer

    def compute_pairwise(
        self,
        seed_product: ProductRepresentation,
        candidate_product: ProductRepresentation,
        *,
        seed_embedding: SemanticVector | None = None,
        candidate_embedding: SemanticVector | None = None,
    ) -> ContentSimilarity:
        rows = self.compute_for_candidates(
            seed_product,
            (
                RecommendationCandidate(
                    product_id=candidate_product.product_id,
                    sources=(RecommendationCandidateSource.VECTOR,),
                    candidate_generation_score=None,
                ),
            ),
            {candidate_product.product_id: candidate_product},
            preloaded_embeddings={
                seed_product.product_id: seed_embedding,
                candidate_product.product_id: candidate_embedding,
            }
            if seed_embedding is not None and candidate_embedding is not None
            else None,
        )
        if not rows:
            msg = "similarity computation produced no rows"
            raise RecommendationError(msg)
        return rows[0]

    def compute_for_candidates(
        self,
        seed_product: ProductRepresentation,
        candidates: Sequence[RecommendationCandidate],
        candidate_products: Mapping[str, ProductRepresentation],
        *,
        preloaded_embeddings: Mapping[str, SemanticVector | None] | None = None,
    ) -> tuple[ContentSimilarity, ...]:
        if not candidates:
            return ()
        candidate_ids = tuple(candidate.product_id for candidate in candidates)
        for product_id in candidate_ids:
            if product_id not in candidate_products:
                msg = f"candidate product context missing for product_id {product_id!r}"
                raise RecommendationError(msg)

        embedding_ids = merge_seed_and_candidate_embedding_ids(seed_product.product_id, candidate_ids)
        embeddings: Mapping[str, SemanticVector]
        if preloaded_embeddings is not None:
            resolved: dict[str, SemanticVector] = {}
            for product_id in embedding_ids:
                vector = preloaded_embeddings.get(product_id)
                if vector is None:
                    msg = f"embedding missing for product_id {product_id!r}"
                    raise CatalogValidationError(msg)
                resolved[product_id] = vector
            embeddings = resolved
        else:
            embeddings = self._embedding_provider.load_embeddings(embedding_ids)

        seed_vector = embeddings[seed_product.product_id]
        lexical_by_id = (
            compute_lexical_similarities(
                seed_product=seed_product,
                candidate_product_ids=candidate_ids,
                scorer=self._bm25_scorer,
            )
            if self._bm25_scorer is not None
            else {}
        )

        rows: list[ContentSimilarity] = []
        for candidate in candidates:
            candidate_product = candidate_products[candidate.product_id]
            candidate_vector = embeddings[candidate.product_id]
            semantic = cosine_similarity(seed_vector, candidate_vector)
            lexical_value = lexical_by_id.get(candidate.product_id)
            structured = compute_structured_product_similarity(seed_product, candidate_product)
            rows.append(
                ContentSimilarity(
                    product_id=candidate.product_id,
                    semantic_similarity=semantic,
                    lexical_similarity=lexical_value,
                    structured=structured,
                )
            )
        return tuple(rows)


__all__ = ["ContentSimilarityEngine"]
