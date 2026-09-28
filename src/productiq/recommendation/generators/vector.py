"""Vector similarity recommendation candidate generator (Phase 11.2)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from productiq.recommendation.contracts import (
    RecommendationCandidate,
    RecommendationCandidateSource,
    RecommendationRequest,
)
from productiq.recommendation.provenance import single_source_candidate
from productiq.representation.schema import ProductRepresentation
from productiq.retrieval.semantic import SemanticVector, VectorIndex


@runtime_checkable
class SeedEmbeddingProvider(Protocol):
    """Load a seed product embedding for vector search."""

    def load_seed_embedding(self, seed_product_id: str) -> SemanticVector:
        """Return the seed embedding or raise when unavailable."""


@dataclass(frozen=True)
class VectorRecommendationCandidateGenerator:
    """Nearest-neighbor catalog search using existing pgvector semantics."""

    vector_index: VectorIndex
    seed_embeddings: SeedEmbeddingProvider

    def generate(
        self,
        request: RecommendationRequest,
        seed_product: ProductRepresentation,
    ) -> tuple[RecommendationCandidate, ...]:
        pool_top_k = request.config.candidate_generation.candidate_pool_top_k
        seed_vector = self.seed_embeddings.load_seed_embedding(seed_product.product_id)
        # Request one extra row so the seed can be filtered without shrinking the pool.
        hits = self.vector_index.search(seed_vector, top_k=pool_top_k + 1)
        rows: list[RecommendationCandidate] = []
        for hit in hits:
            if hit.product_id == seed_product.product_id:
                continue
            rows.append(
                single_source_candidate(
                    product_id=hit.product_id,
                    source=RecommendationCandidateSource.VECTOR,
                    candidate_generation_score=hit.similarity,
                )
            )
            if len(rows) >= pool_top_k:
                break
        return tuple(rows)


def vector_generator_satisfies_protocol(generator: VectorRecommendationCandidateGenerator) -> bool:
    from productiq.recommendation.generators.protocol import RecommendationCandidateGenerator

    return isinstance(generator, RecommendationCandidateGenerator)


__all__ = [
    "SeedEmbeddingProvider",
    "VectorRecommendationCandidateGenerator",
    "vector_generator_satisfies_protocol",
]
