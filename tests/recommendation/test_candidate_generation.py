"""Tests for Phase 11.2 recommendation candidate generation."""

from __future__ import annotations

import math

import pytest

from productiq.exceptions import CatalogValidationError, RecommendationError
from productiq.recommendation.candidate_generation import (
    exclude_seed_product,
    generate_recommendation_candidates,
)
from productiq.recommendation.config import (
    DEFAULT_CANDIDATE_POOL_TOP_K,
    RecommendationCandidateGenerationConfig,
    RecommendationConfig,
)
from productiq.recommendation.contracts import (
    RecommendationCandidate,
    RecommendationCandidateSource,
    RecommendationRequest,
    RecommendationType,
)
from productiq.recommendation.generators.attribute import (
    AttributeRecommendationCandidateGenerator,
    attribute_generation_score,
)
from productiq.recommendation.generators.bm25 import BM25RecommendationCandidateGenerator
from productiq.recommendation.generators.vector import VectorRecommendationCandidateGenerator
from productiq.recommendation.provenance import (
    merge_recommendation_candidates,
    single_source_candidate,
)
from productiq.recommendation.seed_embedding import InMemorySeedEmbeddingProvider
from productiq.recommendation.seed_product import InMemoryRecommendationCatalog
from productiq.representation.filtering import FilteringRepresentation
from productiq.representation.query_contract import QueryFilterConstraints
from productiq.representation.schema import ProductRepresentation
from productiq.retrieval import LexicalIndexDocument, build_inverted_lexical_index
from productiq.retrieval.semantic import SemanticSearchHit, SemanticVector


def _product(
    product_id: str,
    *,
    brand: str | None = "nike",
    category_gender: str = "Women",
    product_type: str | None = "t_shirt",
    color: list[str] | None = None,
) -> ProductRepresentation:
    return ProductRepresentation(
        product_id=product_id,
        brand=brand,
        brand_normalized=brand,
        category_gender=category_gender,
        product_type=product_type,
        color=color or ["black"],
    )


def _filtering(product_id: str, *, category_gender: str = "Women", brand: str = "nike") -> FilteringRepresentation:
    return FilteringRepresentation(
        product_id=product_id,
        source="ajio",
        brand=brand,
        brand_normalized=brand,
        category_gender=category_gender,
        product_type="t_shirt",
        color_raw="black",
        color_is_coded=True,
        color=["black"],
        pattern=None,
        material=None,
        fit=None,
        sleeve=None,
        neckline=None,
        product_features=None,
        style_attributes=None,
        discount_price_inr=1000,
        original_price_inr=1200,
        price_anomaly=False,
    )


def _request(
    seed: str = "P1",
    *,
    pool_top_k: int = DEFAULT_CANDIDATE_POOL_TOP_K,
    filters: QueryFilterConstraints | None = None,
) -> RecommendationRequest:
    config = RecommendationConfig(
        candidate_generation=RecommendationCandidateGenerationConfig(candidate_pool_top_k=pool_top_k)
    )
    return RecommendationRequest(
        seed_product_id=seed,
        recommendation_type=RecommendationType.SIMILAR,
        top_k=10,
        filters=filters,
        config=config,
    )


class _FakeVectorIndex:
    def __init__(self, hits: tuple[SemanticSearchHit, ...]) -> None:
        self._hits = hits

    def search(self, query_vector: SemanticVector, *, top_k: int) -> tuple[SemanticSearchHit, ...]:
        _ = query_vector
        return self._hits[:top_k]


def test_candidate_generation_config_defaults() -> None:
    config = RecommendationCandidateGenerationConfig()
    assert config.candidate_pool_top_k == 50
    assert config.max_candidate_pool_top_k == 200


def test_merge_deduplicates_and_preserves_multi_source_provenance() -> None:
    vector_rows = (
        single_source_candidate(product_id="C", source=RecommendationCandidateSource.VECTOR, candidate_generation_score=0.9),
        single_source_candidate(product_id="A", source=RecommendationCandidateSource.VECTOR, candidate_generation_score=0.8),
    )
    attribute_rows = (
        single_source_candidate(product_id="C", source=RecommendationCandidateSource.ATTRIBUTE, candidate_generation_score=0.4),
        single_source_candidate(product_id="E", source=RecommendationCandidateSource.ATTRIBUTE, candidate_generation_score=0.3),
    )
    bm25_rows = (
        single_source_candidate(product_id="B", source=RecommendationCandidateSource.BM25, candidate_generation_score=1.1),
        single_source_candidate(product_id="C", source=RecommendationCandidateSource.BM25, candidate_generation_score=0.7),
    )
    merged = merge_recommendation_candidates(vector_rows, attribute_rows, bm25_rows)
    by_id = {row.product_id: row for row in merged}
    assert set(by_id) == {"A", "B", "C", "E"}
    assert by_id["C"].sources == (
        RecommendationCandidateSource.ATTRIBUTE,
        RecommendationCandidateSource.BM25,
        RecommendationCandidateSource.VECTOR,
    )
    assert by_id["C"].candidate_generation_score == pytest.approx(0.9)


def test_vector_generator_excludes_seed_and_preserves_similarity() -> None:
    catalog = InMemoryRecommendationCatalog(
        [_product("P1"), _product("P2"), _product("P3")],
    )
    seed = catalog.resolve_seed_product("P1")
    hits = (
        SemanticSearchHit(product_id="P1", similarity=1.0),
        SemanticSearchHit(product_id="P2", similarity=0.91),
        SemanticSearchHit(product_id="P3", similarity=0.90),
    )
    generator = VectorRecommendationCandidateGenerator(
        vector_index=_FakeVectorIndex(hits),
        seed_embeddings=InMemorySeedEmbeddingProvider(
            {"P1": SemanticVector(values=(1.0, 0.0, 0.0))},
        ),
    )
    rows = generator.generate(_request(pool_top_k=2), seed)
    assert [row.product_id for row in rows] == ["P2", "P3"]
    assert rows[0].sources == (RecommendationCandidateSource.VECTOR,)
    assert rows[0].candidate_generation_score == pytest.approx(0.91)


def test_bm25_generator_uses_seed_lexical_text() -> None:
    index = build_inverted_lexical_index(
        [
            LexicalIndexDocument(product_id="P1", lexical_text="nike black running shoes women"),
            LexicalIndexDocument(product_id="P2", lexical_text="nike black shoes women"),
            LexicalIndexDocument(product_id="P3", lexical_text="adidas sandals women"),
        ]
    )
    generator = BM25RecommendationCandidateGenerator(index)
    seed = _product("P1")
    rows = generator.generate(_request(pool_top_k=5), seed)
    product_ids = [row.product_id for row in rows]
    assert "P1" not in product_ids
    assert "P2" in product_ids
    assert all(row.sources == (RecommendationCandidateSource.BM25,) for row in rows)
    assert all(math.isfinite(row.candidate_generation_score or 0.0) for row in rows)


def test_attribute_generator_matches_structured_fields() -> None:
    catalog = InMemoryRecommendationCatalog(
        [
            _product("P1", brand="nike", color=["black"]),
            _product("P2", brand="nike", color=["black"]),
            _product("P3", brand="adidas", color=["black"], category_gender="Men"),
        ]
    )
    generator = AttributeRecommendationCandidateGenerator(catalog)
    seed = catalog.resolve_seed_product("P1")
    rows = generator.generate(_request(pool_top_k=5), seed)
    assert [row.product_id for row in rows] == ["P2"]
    assert rows[0].sources == (RecommendationCandidateSource.ATTRIBUTE,)
    assert attribute_generation_score(seed, _product("P3", category_gender="Men")) == 0.0


def test_orchestrator_applies_constraints_and_seed_exclusion() -> None:
    catalog = InMemoryRecommendationCatalog([_product("P1"), _product("P2"), _product("P3")])
    vector = VectorRecommendationCandidateGenerator(
        vector_index=_FakeVectorIndex(
            (
                SemanticSearchHit(product_id="P1", similarity=1.0),
                SemanticSearchHit(product_id="P2", similarity=0.95),
                SemanticSearchHit(product_id="P3", similarity=0.5),
            )
        ),
        seed_embeddings=InMemorySeedEmbeddingProvider({"P1": SemanticVector(values=(1.0,))}),
    )
    filtering = {
        "P2": _filtering("P2"),
        "P3": _filtering("P3", brand="adidas"),
    }
    result = generate_recommendation_candidates(
        _request("P1", filters=QueryFilterConstraints(brand="nike")),
        catalog=catalog,
        generators=(vector,),
        filtering_by_product_id=filtering,
    )
    assert result.returned_candidate_count == 1
    assert result.candidates[0].product_id == "P2"


def test_invalid_seed_raises_catalog_error() -> None:
    catalog = InMemoryRecommendationCatalog([_product("P1")])
    with pytest.raises(CatalogValidationError):
        generate_recommendation_candidates(
            _request("MISSING"),
            catalog=catalog,
            generators=(),
            filtering_by_product_id={},
        )


def test_generator_failure_fail_fast() -> None:
    class _BrokenGenerator:
        def generate(self, request, seed_product):
            raise RuntimeError("boom")

    catalog = InMemoryRecommendationCatalog([_product("P1")])
    with pytest.raises(RecommendationError, match="generator failed"):
        generate_recommendation_candidates(
            _request("P1"),
            catalog=catalog,
            generators=(_BrokenGenerator(),),
            filtering_by_product_id={},
        )


def test_exclude_seed_product_defensive_filter() -> None:
    rows = (
        RecommendationCandidate(
            product_id="P123",
            sources=(RecommendationCandidateSource.VECTOR,),
            candidate_generation_score=0.5,
        ),
    )
    filtered = exclude_seed_product(rows, seed_product_id="P123")
    assert filtered == ()
