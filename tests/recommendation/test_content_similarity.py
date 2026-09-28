"""Tests for Phase 11.3 content-based similarity."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from productiq.exceptions import CatalogValidationError, RecommendationError, SemanticRetrievalError
from productiq.recommendation.attribute_similarity import (
    jaccard_similarity,
    scalar_attribute_similarity,
)
from productiq.recommendation.catalog_embeddings import (
    InMemoryProductEmbeddingProvider,
    merge_seed_and_candidate_embedding_ids,
)
from productiq.recommendation.content_similarity_engine import ContentSimilarityEngine
from productiq.recommendation.contracts import (
    RecommendationCandidate,
    RecommendationCandidateSource,
)
from productiq.recommendation.similarity_schema import ContentSimilarity
from productiq.representation.lexical import build_structured_lexical_text
from productiq.representation.schema import ProductRepresentation
from productiq.retrieval import LexicalIndexDocument, build_inverted_lexical_index
from productiq.retrieval.bm25 import BM25Scorer
from productiq.retrieval.semantic import SemanticVector, cosine_similarity


def _product(
    product_id: str,
    *,
    brand: str | None = "nike",
    category_gender: str = "Women",
    product_type: str | None = "t_shirt",
    color: list[str] | None = None,
    material: list[str] | None = None,
) -> ProductRepresentation:
    return ProductRepresentation(
        product_id=product_id,
        brand=brand,
        brand_normalized=brand,
        category_gender=category_gender,
        product_type=product_type,
        color=color or ["black"],
        material=material,
    )


def _unit_vector(axis: int, dim: int = 3) -> SemanticVector:
    values = [0.0] * dim
    values[axis] = 1.0
    return SemanticVector(values=tuple(values))


def _candidate(product_id: str) -> RecommendationCandidate:
    return RecommendationCandidate(
        product_id=product_id,
        sources=(RecommendationCandidateSource.VECTOR,),
        candidate_generation_score=0.42,
    )


class TestScalarAttributeSimilarity:
    def test_same_value(self) -> None:
        assert scalar_attribute_similarity("Nike", "nike") == 1.0

    def test_different_value(self) -> None:
        assert scalar_attribute_similarity("nike", "adidas") == 0.0

    def test_missing_seed(self) -> None:
        assert scalar_attribute_similarity(None, "nike") is None

    def test_missing_candidate(self) -> None:
        assert scalar_attribute_similarity("nike", None) is None

    def test_both_missing(self) -> None:
        assert scalar_attribute_similarity(None, None) is None


class TestJaccardSimilarity:
    def test_identical(self) -> None:
        assert jaccard_similarity(["Red", "Blue"], ["red", "blue"]) == 1.0

    def test_partial_overlap(self) -> None:
        assert jaccard_similarity(["a", "b"], ["b", "c"]) == pytest.approx(1 / 3)

    def test_no_overlap(self) -> None:
        assert jaccard_similarity(["a"], ["b"]) == 0.0

    def test_missing(self) -> None:
        assert jaccard_similarity(None, ["a"]) is None
        assert jaccard_similarity(["a"], None) is None
        assert jaccard_similarity(None, None) is None


class TestSemanticSimilarity:
    def test_identical_unit_vectors(self) -> None:
        vector = _unit_vector(0)
        assert cosine_similarity(vector, vector) == pytest.approx(1.0)

    def test_orthogonal_vectors(self) -> None:
        assert cosine_similarity(_unit_vector(0), _unit_vector(1)) == pytest.approx(0.0)

    def test_dimension_mismatch_raises(self) -> None:
        with pytest.raises(SemanticRetrievalError, match="matching vector dimension"):
            cosine_similarity(SemanticVector(values=(1.0, 0.0)), SemanticVector(values=(1.0, 0.0, 0.0)))

    def test_non_finite_raises(self) -> None:
        with pytest.raises(SemanticRetrievalError, match="finite"):
            cosine_similarity((float("nan"), 1.0), (1.0, 0.0))


class TestLexicalSimilarity:
    def _scorer_for_products(self, *products: ProductRepresentation) -> BM25Scorer:
        docs = [
            LexicalIndexDocument(
                product_id=product.product_id,
                lexical_text=build_structured_lexical_text(product),
            )
            for product in products
        ]
        return BM25Scorer(build_inverted_lexical_index(docs))

    def test_identical_lexical_content_scores_positive(self) -> None:
        seed = _product("S1")
        candidate = _product("C1", brand="nike", color=["black"])
        engine = ContentSimilarityEngine(
            embedding_provider=InMemoryProductEmbeddingProvider(
                {
                    "S1": _unit_vector(0),
                    "C1": _unit_vector(0),
                }
            ),
            bm25_scorer=self._scorer_for_products(seed, candidate),
        )
        row = engine.compute_pairwise(seed, candidate)
        assert row.lexical_similarity is not None
        assert row.lexical_similarity > 0.0

    def test_no_bm25_scorer_yields_none_lexical(self) -> None:
        seed = _product("S1")
        candidate = _product("C1")
        engine = ContentSimilarityEngine(
            embedding_provider=InMemoryProductEmbeddingProvider(
                {"S1": _unit_vector(0), "C1": _unit_vector(1)}
            ),
        )
        row = engine.compute_pairwise(seed, candidate)
        assert row.lexical_similarity is None


class TestContentSimilarityEngineBatch:
    def test_batch_matches_pairwise(self) -> None:
        seed = _product("S1")
        c1 = _product("C1", color=["black"])
        c2 = _product("C2", color=["white"])
        provider = InMemoryProductEmbeddingProvider(
            {
                "S1": _unit_vector(0),
                "C1": _unit_vector(0),
                "C2": _unit_vector(1),
            }
        )
        engine = ContentSimilarityEngine(embedding_provider=provider)
        pairwise_c1 = engine.compute_pairwise(seed, c1)
        pairwise_c2 = engine.compute_pairwise(seed, c2)
        batch = engine.compute_for_candidates(
            seed,
            (_candidate("C1"), _candidate("C2")),
            {"C1": c1, "C2": c2},
        )
        assert batch[0] == pairwise_c1
        assert batch[1] == pairwise_c2

    def test_single_batch_embedding_lookup(self) -> None:
        seed = _product("S1")
        candidates = (_candidate(f"C{i}") for i in range(1, 4))
        products = {f"C{i}": _product(f"C{i}") for i in range(1, 4)}
        provider = InMemoryProductEmbeddingProvider(
            {
                "S1": _unit_vector(0),
                **{f"C{i}": _unit_vector(i % 3) for i in range(1, 4)},
            }
        )
        engine = ContentSimilarityEngine(embedding_provider=provider)
        engine.compute_for_candidates(seed, tuple(candidates), products)
        assert provider.load_call_count == 1
        assert provider.last_requested_ids == merge_seed_and_candidate_embedding_ids(
            "S1",
            ("C1", "C2", "C3"),
        )

    def test_missing_candidate_context_raises(self) -> None:
        seed = _product("S1")
        provider = InMemoryProductEmbeddingProvider({"S1": _unit_vector(0), "C1": _unit_vector(1)})
        engine = ContentSimilarityEngine(embedding_provider=provider)
        with pytest.raises(RecommendationError, match="candidate product context missing"):
            engine.compute_for_candidates(seed, (_candidate("C1"),), {})

    def test_missing_embedding_raises(self) -> None:
        seed = _product("S1")
        candidate = _product("C1")
        provider = InMemoryProductEmbeddingProvider({"S1": _unit_vector(0)})
        engine = ContentSimilarityEngine(embedding_provider=provider)
        with pytest.raises(CatalogValidationError, match="embedding missing"):
            engine.compute_for_candidates(seed, (_candidate("C1"),), {"C1": candidate})

    def test_structured_missing_brand_is_none_not_zero(self) -> None:
        seed = _product("S1", brand=None)
        candidate = _product("C1", brand="nike")
        engine = ContentSimilarityEngine(
            embedding_provider=InMemoryProductEmbeddingProvider(
                {"S1": _unit_vector(0), "C1": _unit_vector(0)}
            ),
        )
        row = engine.compute_pairwise(seed, candidate)
        assert row.structured.scalars.brand is None


class TestContentSimilarityContract:
    def test_immutable(self) -> None:
        row = ContentSimilarity(product_id="P1", semantic_similarity=0.5)
        with pytest.raises(ValidationError):
            row.semantic_similarity = 0.6  # type: ignore[misc]

    def test_non_finite_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ContentSimilarity(product_id="P1", semantic_similarity=float("inf"))

    def test_deterministic_serialization(self) -> None:
        row = ContentSimilarity(product_id="P1", semantic_similarity=0.25)
        assert row.model_dump(mode="json") == row.model_dump(mode="json")

    def test_generation_score_not_copied(self) -> None:
        seed = _product("S1")
        candidate = _product("C1")
        engine = ContentSimilarityEngine(
            embedding_provider=InMemoryProductEmbeddingProvider(
                {"S1": _unit_vector(0), "C1": _unit_vector(0)}
            ),
        )
        row = engine.compute_for_candidates(
            seed,
            (_candidate("C1"),),
            {"C1": candidate},
        )[0]
        assert row.semantic_similarity == pytest.approx(1.0)
        assert "candidate_generation_score" not in row.model_dump()


def test_merge_embedding_ids_deduplicates_seed_when_in_candidates() -> None:
    merged = merge_seed_and_candidate_embedding_ids("S1", ("C1", "S1", "C2"))
    assert merged == ("S1", "C1", "C2")
