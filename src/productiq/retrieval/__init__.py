"""Search and retrieval contracts (Phase 4.2).

Public symbols are loaded lazily so submodules (e.g. ``embedding_encoder``) can be
imported without initializing the full lexical/BM25 stack or Phase 1 data pipelines.
"""

from __future__ import annotations

import importlib
from typing import Any

__all__ = [
    "DEFAULT_EVALUATION_K_VALUES",
    "PRODUCT_FILTERING_RETRIEVAL_MODEL",
    "PRODUCT_LEXICAL_RETRIEVAL_FIELD",
    "PRODUCT_SEMANTIC_RETRIEVAL_FIELD",
    "RETRIEVAL_PRODUCT_QUERY_ALIGNMENT",
    "RETRIEVAL_QUERY_VIEW_FIELD_ORDER",
    "BM25Config",
    "BM25CorpusStatistics",
    "BM25LexicalIndexBuildResult",
    "BM25LexicalIndexManifest",
    "BM25Retriever",
    "BM25ScoredCandidate",
    "BM25Scorer",
    "HybridRetriever",
    "InvertedLexicalIndex",
    "LexicalIndexDocument",
    "LexicalIndexStatistics",
    "LexicalPosting",
    "LexicalRetrievalBenchmark",
    "LexicalRetrievalEvaluationResult",
    "LexicalRetrievalEvaluator",
    "PgVectorProductVectorIndex",
    "ProductIQEmbeddingModelSelection",
    "ProductionRetrievalConfig",
    "ProductionRetrievalPipeline",
    "RRFConfig",
    "RRFHybridRetriever",
    "RetrievalCandidate",
    "RetrievalError",
    "RetrievalMethod",
    "RetrievalQueryView",
    "RetrievalRequest",
    "RetrievalResponse",
    "RetrievalResponseMetadata",
    "Retriever",
    "SemanticRetrievalConfig",
    "SemanticRetriever",
    "SemanticSearchHit",
    "SemanticSimilarityMetric",
    "SemanticVector",
    "VectorIndex",
    "apply_bm25_top_k",
    "assemble_inverted_lexical_index",
    "bm25_idf",
    "bm25_scored_candidates_to_dict",
    "build_bm25_lexical_index_from_representation_dataset",
    "build_inverted_lexical_index",
    "build_inverted_lexical_index_from_mapping",
    "build_retrieval_query_view",
    "compute_lexical_index_statistics",
    "cosine_similarity",
    "create_bm25_retriever",
    "create_bm25_retriever_from_index_path",
    "create_hybrid_retriever",
    "create_pgvector_product_vector_index",
    "create_production_retrieval_pipeline",
    "create_production_retrieval_pipeline_from_retrievers",
    "create_rrf_hybrid_retriever",
    "create_semantic_retriever",
    "create_semantic_retriever_from_engine",
    "inverted_lexical_index_to_dict",
    "load_bm25_lexical_index_manifest",
    "load_inverted_lexical_index",
    "load_lexical_retrieval_benchmark",
    "load_productiq_embedding_model_selection",
    "normalize_lexical_query_term",
    "normalize_lexical_surface_text",
    "precision_at_k",
    "query_constraints_align_with_filtering_representation",
    "query_has_usable_retrieval_intent",
    "rank_bm25_scored_candidates",
    "recall_at_k",
    "retrieval_query_view_to_dict",
    "retrieval_request_to_dict",
    "retrieval_response_to_dict",
    "retrieve_lexical_candidates",
    "retrieve_lexical_candidates_from_view",
    "save_inverted_lexical_index",
    "score_bm25_from_retrieval_request",
    "score_bm25_from_view",
    "score_bm25_lexical_query",
    "semantic_retrieval_candidate",
    "semantic_retrieval_text_from_query",
    "semantic_retrieval_text_from_request",
    "semantic_vector_from_sequence",
    "tokenize_lexical_text",
    "unique_lexical_query_terms",
    "validate_inverted_lexical_index_integrity",
]


def _lazy(module: str, *names: str) -> dict[str, tuple[str, str]]:
    return {name: (module, name) for name in names}


_LAZY_EXPORTS: dict[str, tuple[str, str]] = {}
_LAZY_EXPORTS.update(
    _lazy(
        "productiq.retrieval.bm25",
        "BM25Config",
        "BM25CorpusStatistics",
        "BM25ScoredCandidate",
        "BM25Scorer",
        "apply_bm25_top_k",
        "bm25_idf",
        "bm25_scored_candidates_to_dict",
        "rank_bm25_scored_candidates",
        "score_bm25_from_retrieval_request",
        "score_bm25_from_view",
        "score_bm25_lexical_query",
        "unique_lexical_query_terms",
    )
)
_LAZY_EXPORTS.update(
    _lazy(
        "productiq.retrieval.bm25_retriever",
        "BM25Retriever",
        "create_bm25_retriever",
        "create_bm25_retriever_from_index_path",
    )
)
_LAZY_EXPORTS.update(
    _lazy(
        "productiq.retrieval.contracts",
        "RetrievalCandidate",
        "RetrievalMethod",
        "RetrievalRequest",
        "RetrievalResponse",
        "RetrievalResponseMetadata",
        "Retriever",
        "retrieval_request_to_dict",
        "retrieval_response_to_dict",
    )
)
_LAZY_EXPORTS.update(
    _lazy(
        "productiq.retrieval.embedding_selection",
        "ProductIQEmbeddingModelSelection",
        "load_productiq_embedding_model_selection",
    )
)
_LAZY_EXPORTS.update(_lazy("productiq.retrieval.exceptions", "RetrievalError"))
_LAZY_EXPORTS.update(
    _lazy(
        "productiq.retrieval.evaluation",
        "DEFAULT_EVALUATION_K_VALUES",
        "LexicalRetrievalBenchmark",
        "LexicalRetrievalEvaluationResult",
        "LexicalRetrievalEvaluator",
        "load_lexical_retrieval_benchmark",
        "precision_at_k",
        "recall_at_k",
    )
)
_LAZY_EXPORTS.update(
    _lazy(
        "productiq.retrieval.index_builder",
        "BM25LexicalIndexBuildResult",
        "BM25LexicalIndexManifest",
        "LexicalIndexStatistics",
        "build_bm25_lexical_index_from_representation_dataset",
        "compute_lexical_index_statistics",
        "load_bm25_lexical_index_manifest",
        "load_inverted_lexical_index",
        "save_inverted_lexical_index",
        "validate_inverted_lexical_index_integrity",
    )
)
_LAZY_EXPORTS.update(
    _lazy(
        "productiq.retrieval.lexical",
        "InvertedLexicalIndex",
        "LexicalIndexDocument",
        "LexicalPosting",
        "assemble_inverted_lexical_index",
        "build_inverted_lexical_index",
        "build_inverted_lexical_index_from_mapping",
        "inverted_lexical_index_to_dict",
        "normalize_lexical_query_term",
        "normalize_lexical_surface_text",
        "retrieve_lexical_candidates",
        "retrieve_lexical_candidates_from_view",
        "tokenize_lexical_text",
    )
)
_LAZY_EXPORTS.update(
    _lazy(
        "productiq.retrieval.query_for_retrieval",
        "PRODUCT_FILTERING_RETRIEVAL_MODEL",
        "PRODUCT_LEXICAL_RETRIEVAL_FIELD",
        "PRODUCT_SEMANTIC_RETRIEVAL_FIELD",
        "RETRIEVAL_PRODUCT_QUERY_ALIGNMENT",
        "RETRIEVAL_QUERY_VIEW_FIELD_ORDER",
        "RetrievalQueryView",
        "build_retrieval_query_view",
        "query_constraints_align_with_filtering_representation",
        "query_has_usable_retrieval_intent",
        "retrieval_query_view_to_dict",
    )
)
_LAZY_EXPORTS.update(
    _lazy(
        "productiq.retrieval.pgvector_vector_index",
        "PgVectorProductVectorIndex",
        "create_pgvector_product_vector_index",
    )
)
_LAZY_EXPORTS.update(
    _lazy(
        "productiq.retrieval.production_config",
        "ProductionRetrievalConfig",
    )
)
_LAZY_EXPORTS.update(
    _lazy(
        "productiq.retrieval.production_pipeline",
        "ProductionRetrievalPipeline",
        "create_production_retrieval_pipeline",
    )
)
_LAZY_EXPORTS.update(
    _lazy(
        "productiq.retrieval.production_factory",
        "create_production_retrieval_pipeline_from_retrievers",
    )
)
_LAZY_EXPORTS.update(
    _lazy(
        "productiq.retrieval.rrf_config",
        "RRFConfig",
    )
)
_LAZY_EXPORTS.update(
    _lazy(
        "productiq.retrieval.rrf_hybrid_retriever",
        "RRFHybridRetriever",
        "create_rrf_hybrid_retriever",
    )
)
_LAZY_EXPORTS.update(
    _lazy(
        "productiq.retrieval.hybrid_retriever",
        "HybridRetriever",
        "create_hybrid_retriever",
    )
)
_LAZY_EXPORTS.update(
    _lazy(
        "productiq.retrieval.semantic_retriever",
        "SemanticRetriever",
        "create_semantic_retriever",
        "create_semantic_retriever_from_engine",
    )
)
_LAZY_EXPORTS.update(
    _lazy(
        "productiq.retrieval.semantic",
        "SemanticRetrievalConfig",
        "SemanticSearchHit",
        "SemanticSimilarityMetric",
        "SemanticVector",
        "VectorIndex",
        "cosine_similarity",
        "semantic_retrieval_candidate",
        "semantic_retrieval_text_from_query",
        "semantic_retrieval_text_from_request",
        "semantic_vector_from_sequence",
    )
)


def __getattr__(name: str) -> Any:
    if name not in _LAZY_EXPORTS:
        msg = f"module {__name__!r} has no attribute {name!r}"
        raise AttributeError(msg)
    module_name, attr_name = _LAZY_EXPORTS[name]
    module = importlib.import_module(module_name)
    return getattr(module, attr_name)


def __dir__() -> list[str]:
    return sorted(__all__)
