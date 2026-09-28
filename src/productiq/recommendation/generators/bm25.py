"""BM25 lexical neighbor recommendation candidate generator (Phase 11.2)."""

from __future__ import annotations

from dataclasses import dataclass

from productiq.recommendation.contracts import (
    RecommendationCandidate,
    RecommendationCandidateSource,
    RecommendationRequest,
)
from productiq.recommendation.provenance import single_source_candidate
from productiq.recommendation.seed_lexical import build_seed_lexical_text
from productiq.representation.schema import ProductRepresentation
from productiq.retrieval.bm25 import BM25Config, BM25Scorer, apply_bm25_top_k
from productiq.retrieval.lexical import InvertedLexicalIndex, retrieve_lexical_candidates


@dataclass(frozen=True)
class BM25RecommendationCandidateGenerator:
    """Lexical neighbors from deterministic seed-product text over the existing BM25 index."""

    index: InvertedLexicalIndex
    scorer: BM25Scorer

    def __init__(
        self,
        index: InvertedLexicalIndex,
        *,
        config: BM25Config | None = None,
        scorer: BM25Scorer | None = None,
    ) -> None:
        object.__setattr__(self, "index", index)
        object.__setattr__(self, "scorer", scorer or BM25Scorer(index, config=config))

    def generate(
        self,
        request: RecommendationRequest,
        seed_product: ProductRepresentation,
    ) -> tuple[RecommendationCandidate, ...]:
        pool_top_k = request.config.candidate_generation.candidate_pool_top_k
        lexical_text = build_seed_lexical_text(seed_product)
        if not lexical_text.strip():
            return ()
        candidate_ids = retrieve_lexical_candidates(self.index, lexical_text)
        if not candidate_ids:
            return ()
        candidate_ids = tuple(
            product_id for product_id in candidate_ids if product_id != seed_product.product_id
        )
        scored = self.scorer.score_lexical_query(
            lexical_text,
            candidate_product_ids=candidate_ids,
        )
        ranked = apply_bm25_top_k(scored, pool_top_k)
        return tuple(
            single_source_candidate(
                product_id=row.product_id,
                source=RecommendationCandidateSource.BM25,
                candidate_generation_score=row.score,
            )
            for row in ranked
            if row.product_id != seed_product.product_id
        )


__all__ = ["BM25RecommendationCandidateGenerator"]
