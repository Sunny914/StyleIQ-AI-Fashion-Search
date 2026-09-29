"""Stable baseline variant identity and lineage metadata (Phase 12.5)."""

from __future__ import annotations

from typing import Any

from productiq.retrieval.evaluation.search_evaluation.baseline_schema import (
    SEARCH_BASELINE_BM25_VARIANT_NAME,
    SEARCH_BASELINE_RRF_VARIANT_NAME,
    SEARCH_BASELINE_SEMANTIC_VARIANT_NAME,
)
from productiq.retrieval.evaluation.search_evaluation.request_schema import SearchEvaluationVariant
from productiq.retrieval.rrf_config import DEFAULT_RRF_RANK_CONSTANT


def bm25_search_evaluation_variant(
    *,
    index_mode: str,
    bm25_manifest: dict[str, Any],
) -> SearchEvaluationVariant:
    schema_version = str(bm25_manifest.get("schema_version", "1.0.0"))
    checksum = str(bm25_manifest.get("checksum", ""))
    return SearchEvaluationVariant(
        variant_name=SEARCH_BASELINE_BM25_VARIANT_NAME,
        variant_version=schema_version,
        description=(
            "ProductIQ BM25 lexical retrieval baseline evaluated on "
            "productiq_search_benchmark_v1."
        ),
        lineage_labels=(
            "retrieval_mode:bm25",
            f"bm25_index_name:{bm25_manifest.get('index_name', 'bm25_lexical_index')}",
            f"bm25_manifest_schema_version:{schema_version}",
            f"bm25_index_checksum:{checksum}",
            f"bm25_index_mode:{index_mode}",
            f"source_representation_checksum:{bm25_manifest.get('source_representation_checksum', '')}",
        ),
    )


def semantic_search_evaluation_variant(
    *,
    vector_index_manifest: dict[str, Any],
) -> SearchEvaluationVariant:
    schema_version = str(vector_index_manifest.get("schema_version", "1.0.0"))
    return SearchEvaluationVariant(
        variant_name=SEARCH_BASELINE_SEMANTIC_VARIANT_NAME,
        variant_version=schema_version,
        description=(
            "ProductIQ semantic vector retrieval baseline (BGE + pgvector HNSW) on "
            "productiq_search_benchmark_v1."
        ),
        lineage_labels=(
            "retrieval_mode:semantic",
            f"embedding_model_id:{vector_index_manifest.get('embedding_model_id', '')}",
            f"embedding_model_revision:{vector_index_manifest.get('embedding_model_revision', '')}",
            f"vector_index_name:{vector_index_manifest.get('index_name', '')}",
            f"vector_index_schema_version:{schema_version}",
            f"source_representation_checksum:{vector_index_manifest.get('source_representation_checksum', '')}",
            f"source_embedding_artifact_checksum:{vector_index_manifest.get('source_embedding_artifact_checksum', '')}",
        ),
    )


def rrf_search_evaluation_variant(
    *,
    bm25_manifest: dict[str, Any],
    vector_index_manifest: dict[str, Any],
    rank_constant: int,
    bm25_index_mode: str,
) -> SearchEvaluationVariant:
    schema_version = "1.0.0"
    return SearchEvaluationVariant(
        variant_name=SEARCH_BASELINE_RRF_VARIANT_NAME,
        variant_version=schema_version,
        description=(
            "ProductIQ RRF hybrid retrieval baseline (BM25 + semantic fusion) on "
            "productiq_search_benchmark_v1."
        ),
        lineage_labels=(
            "retrieval_mode:rrf_hybrid",
            f"rrf_rank_constant:{rank_constant}",
            f"bm25_index_checksum:{bm25_manifest.get('checksum', '')}",
            f"bm25_index_mode:{bm25_index_mode}",
            f"embedding_model_id:{vector_index_manifest.get('embedding_model_id', '')}",
            f"embedding_model_revision:{vector_index_manifest.get('embedding_model_revision', '')}",
            f"vector_index_name:{vector_index_manifest.get('index_name', '')}",
        ),
    )


def bm25_retrieval_provenance(
    *,
    index_mode: str,
    bm25_manifest: dict[str, Any],
    index_path: str,
) -> dict[str, Any]:
    return {
        "retrieval_mode": "bm25",
        "index_mode": index_mode,
        "index_path": index_path,
        "bm25_manifest": bm25_manifest,
    }


def semantic_retrieval_provenance(
    *,
    vector_index_manifest: dict[str, Any],
) -> dict[str, Any]:
    return {
        "retrieval_mode": "semantic",
        "similarity_metric": vector_index_manifest.get("distance_metric", "cosine"),
        "vector_index_manifest": vector_index_manifest,
    }


def rrf_retrieval_provenance(
    *,
    bm25_manifest: dict[str, Any],
    vector_index_manifest: dict[str, Any],
    rank_constant: int,
    bm25_index_mode: str,
) -> dict[str, Any]:
    return {
        "retrieval_mode": "rrf_hybrid",
        "rrf_rank_constant": rank_constant,
        "default_rrf_rank_constant": DEFAULT_RRF_RANK_CONSTANT,
        "bm25_index_mode": bm25_index_mode,
        "bm25_manifest": bm25_manifest,
        "vector_index_manifest": vector_index_manifest,
    }


__all__ = [
    "bm25_retrieval_provenance",
    "bm25_search_evaluation_variant",
    "rrf_retrieval_provenance",
    "rrf_search_evaluation_variant",
    "semantic_retrieval_provenance",
    "semantic_search_evaluation_variant",
]
