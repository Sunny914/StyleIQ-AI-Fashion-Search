"""Real ProductIQ retriever wiring for Phase 12.5 baseline evaluation."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from productiq.retrieval import create_bm25_retriever_from_index_path
from productiq.retrieval.contracts import Retriever
from productiq.retrieval.evaluation.benchmark_index import build_benchmark_scoped_bm25_retriever
from productiq.retrieval.evaluation.dataset import load_lexical_retrieval_benchmark
from productiq.retrieval.evaluation.schema import LEXICAL_RETRIEVAL_BENCHMARK_FILENAME
from productiq.retrieval.evaluation.search_evaluation.benchmark_schema import (
    SearchEvaluationBenchmark,
)
from productiq.retrieval.evaluation.search_evaluation.retriever_executor import (
    RetrieverSearchEvaluationExecutor,
)
from productiq.retrieval.rrf_config import RRFConfig
from productiq.retrieval.rrf_hybrid_retriever import create_rrf_hybrid_retriever
from productiq.retrieval.semantic_retriever import (
    SemanticRetriever,
    create_semantic_retriever_from_engine,
)


def _read_json_manifest(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        msg = f"manifest must be a JSON object: {path}"
        raise TypeError(msg)
    return payload


@dataclass(frozen=True, slots=True)
class Bm25BaselineSetup:
    executor: RetrieverSearchEvaluationExecutor
    index_mode: str
    bm25_manifest: dict[str, Any]
    index_path: Path


def create_bm25_baseline_setup(
    repo_root: Path,
    *,
    search_benchmark: SearchEvaluationBenchmark | None = None,
) -> Bm25BaselineSetup:
    """Load BM25 retriever for baseline evaluation (full index with scoped fallback)."""
    root = Path(repo_root)
    index_path = root / "resources" / "processed" / "bm25_lexical_index.pkl"
    manifest_path = root / "resources" / "processed" / "bm25_lexical_index.manifest.json"
    parquet_path = root / "resources" / "processed" / "product_representations.parquet"
    bm25_manifest = _read_json_manifest(manifest_path)

    if os.environ.get("PRODUCTIQ_SEARCH_BASELINE_BM25_SCOPED") == "1":
        lexical_benchmark = load_lexical_retrieval_benchmark(
            root / "resources" / "evaluation" / LEXICAL_RETRIEVAL_BENCHMARK_FILENAME
        )
        retriever, doc_count = build_benchmark_scoped_bm25_retriever(
            parquet_path,
            lexical_benchmark,
            max_docs_per_term=500,
            max_total_docs=8_000,
        )
        index_mode = f"benchmark_scoped_slice_{doc_count}_docs"
    else:
        try:
            retriever = create_bm25_retriever_from_index_path(index_path)
            index_mode = "full_persisted_index"
        except MemoryError:
            lexical_benchmark = load_lexical_retrieval_benchmark(
                root / "resources" / "evaluation" / LEXICAL_RETRIEVAL_BENCHMARK_FILENAME
            )
            retriever, doc_count = build_benchmark_scoped_bm25_retriever(
                parquet_path,
                lexical_benchmark,
                max_docs_per_term=500,
                max_total_docs=8_000,
            )
            index_mode = f"benchmark_scoped_slice_{doc_count}_docs"

    _ = search_benchmark  # reserved for future catalog-scoped alignment checks
    return Bm25BaselineSetup(
        executor=RetrieverSearchEvaluationExecutor(retriever),
        index_mode=index_mode,
        bm25_manifest=bm25_manifest,
        index_path=index_path,
    )


@dataclass(frozen=True, slots=True)
class SemanticBaselineSetup:
    executor: RetrieverSearchEvaluationExecutor
    vector_index_manifest: dict[str, Any]
    semantic_retriever: SemanticRetriever


def create_semantic_baseline_setup(
    repo_root: Path,
    *,
    engine: Any,
    encoder: Any,
) -> SemanticBaselineSetup:
    root = Path(repo_root)
    manifest_path = root / "resources" / "processed" / "product_vector_index.manifest.json"
    vector_index_manifest = _read_json_manifest(manifest_path)
    semantic_retriever = create_semantic_retriever_from_engine(engine, encoder)
    return SemanticBaselineSetup(
        executor=RetrieverSearchEvaluationExecutor(semantic_retriever),
        vector_index_manifest=vector_index_manifest,
        semantic_retriever=semantic_retriever,
    )


@dataclass(frozen=True, slots=True)
class RrfBaselineSetup:
    executor: RetrieverSearchEvaluationExecutor
    bm25_manifest: dict[str, Any]
    vector_index_manifest: dict[str, Any]
    bm25_index_mode: str
    rrf_config: RRFConfig


def create_rrf_baseline_setup(
    repo_root: Path,
    *,
    bm25_retriever: Retriever,
    semantic_retriever: SemanticRetriever,
    bm25_index_mode: str,
    rrf_config: RRFConfig | None = None,
) -> RrfBaselineSetup:
    root = Path(repo_root)
    config = rrf_config or RRFConfig()
    hybrid = create_rrf_hybrid_retriever(bm25_retriever, semantic_retriever, config=config)
    bm25_manifest = _read_json_manifest(
        root / "resources" / "processed" / "bm25_lexical_index.manifest.json"
    )
    vector_index_manifest = _read_json_manifest(
        root / "resources" / "processed" / "product_vector_index.manifest.json"
    )
    return RrfBaselineSetup(
        executor=RetrieverSearchEvaluationExecutor(hybrid),
        bm25_manifest=bm25_manifest,
        vector_index_manifest=vector_index_manifest,
        bm25_index_mode=bm25_index_mode,
        rrf_config=config,
    )


__all__ = [
    "Bm25BaselineSetup",
    "RrfBaselineSetup",
    "SemanticBaselineSetup",
    "create_bm25_baseline_setup",
    "create_rrf_baseline_setup",
    "create_semantic_baseline_setup",
]
