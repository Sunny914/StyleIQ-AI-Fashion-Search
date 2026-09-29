"""Convert Phase 4.8 lexical benchmarks into SearchEvaluationBenchmark (Phase 12.2)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from productiq.exceptions.base import RetrievalError
from productiq.retrieval.evaluation.dataset import (
    LexicalEvaluationQuery,
    LexicalRetrievalBenchmark,
    load_lexical_retrieval_benchmark,
)
from productiq.retrieval.evaluation.search_evaluation.benchmark_artifact_schema import (
    DEFAULT_LEGACY_BINARY_RELEVANT_GRADE,
)
from productiq.retrieval.evaluation.search_evaluation.benchmark_integrity import (
    validate_search_benchmark_integrity,
)
from productiq.retrieval.evaluation.search_evaluation.benchmark_schema import (
    SearchEvaluationBenchmark,
    SearchEvaluationBenchmarkMetadata,
    SearchEvaluationQuery,
    SearchRelevanceJudgment,
    lexical_query_to_search_evaluation_query,
)


def _labeling_methodology_for_legacy_conversion(
    *,
    benchmark_name: str,
    binary_relevant_grade: int,
    deduplicated_by_loader: bool,
) -> str:
    dedupe_note = (
        "Product IDs were normalized by the Phase 4.8 lexical loader "
        "(strip whitespace; drop duplicate IDs within each query while preserving first-seen order)."
        if deduplicated_by_loader
        else "Product IDs were taken from the legacy JSON payload in file order without deduplication."
    )
    return (
        f"Legacy binary relevant_product_ids from {benchmark_name} mapped to graded judgments "
        f"with grade={binary_relevant_grade} (minimum relevant threshold for P/R/MRR in legacy "
        f"evaluation). {dedupe_note} No silent drops beyond documented normalization."
    )


def convert_lexical_retrieval_benchmark_to_search(
    benchmark: LexicalRetrievalBenchmark,
    *,
    binary_relevant_grade: int = DEFAULT_LEGACY_BINARY_RELEVANT_GRADE,
) -> SearchEvaluationBenchmark:
    """Adapt a loaded LexicalRetrievalBenchmark (deduped IDs) to graded search contracts."""
    queries = tuple(
        lexical_query_to_search_evaluation_query(
            query_id=query.query_id,
            query_text=query.query_text,
            category=query.category,
            relevant_product_ids=query.relevant_product_ids,
            binary_relevant_grade=binary_relevant_grade,
        )
        for query in benchmark.queries
    )
    metadata = SearchEvaluationBenchmarkMetadata(
        benchmark_name=benchmark.benchmark_name,
        benchmark_version=benchmark.benchmark_version,
        catalog_artifact=benchmark.catalog_artifact,
        source_representation_checksum=benchmark.source_representation_checksum,
        methodology=benchmark.methodology,
        labeling_methodology=_labeling_methodology_for_legacy_conversion(
            benchmark_name=benchmark.benchmark_name,
            binary_relevant_grade=binary_relevant_grade,
            deduplicated_by_loader=True,
        ),
        limitations=benchmark.limitations,
    )
    converted = SearchEvaluationBenchmark(metadata=metadata, queries=queries)
    validate_search_benchmark_integrity(converted)
    return converted


def _lexical_query_from_payload_row(
    row: dict[str, Any],
    *,
    binary_relevant_grade: int,
) -> SearchEvaluationQuery:
    query_id = str(row.get("query_id", "")).strip()
    query_text = str(row.get("query_text", "")).strip()
    category = str(row.get("category", "general")).strip() or "general"
    raw_ids = row.get("relevant_product_ids")
    if not isinstance(raw_ids, list):
        msg = "legacy query relevant_product_ids must be a JSON array"
        raise RetrievalError(msg)
    judgments: list[SearchRelevanceJudgment] = []
    for raw in raw_ids:
        product_id = str(raw).strip()
        if not product_id:
            msg = f"empty product_id in legacy query {query_id!r}"
            raise RetrievalError(msg)
        judgments.append(
            SearchRelevanceJudgment(product_id=product_id, grade=binary_relevant_grade)
        )
    try:
        return SearchEvaluationQuery(
            query_id=query_id,
            query_text=query_text,
            query_category=category,
            relevance_judgments=tuple(judgments),
        )
    except ValidationError as exc:
        msg = f"invalid legacy query row {query_id!r}: {exc}"
        raise RetrievalError(msg) from exc


def convert_lexical_benchmark_payload_to_search(
    payload: dict[str, Any],
    *,
    binary_relevant_grade: int = DEFAULT_LEGACY_BINARY_RELEVANT_GRADE,
) -> SearchEvaluationBenchmark:
    """Adapt raw lexical benchmark JSON (file order, no loader dedupe) to graded search contracts."""
    if not isinstance(payload, dict):
        msg = "legacy lexical benchmark payload must be a JSON object"
        raise RetrievalError(msg)
    raw_queries = payload.get("queries")
    if not isinstance(raw_queries, list) or not raw_queries:
        msg = "legacy lexical benchmark must contain a non-empty queries array"
        raise RetrievalError(msg)
    queries: list[SearchEvaluationQuery] = []
    for row in raw_queries:
        if not isinstance(row, dict):
            msg = "each legacy query must be a JSON object"
            raise RetrievalError(msg)
        queries.append(
            _lexical_query_from_payload_row(row, binary_relevant_grade=binary_relevant_grade)
        )
    try:
        metadata = SearchEvaluationBenchmarkMetadata(
            benchmark_name=str(payload.get("benchmark_name", "")).strip(),
            benchmark_version=str(payload.get("benchmark_version", "")).strip(),
            catalog_artifact=str(payload.get("catalog_artifact", "")).strip() or None,
            source_representation_checksum=payload.get("source_representation_checksum"),
            methodology=str(payload.get("methodology", "")).strip(),
            labeling_methodology=_labeling_methodology_for_legacy_conversion(
                benchmark_name=str(payload.get("benchmark_name", "")).strip(),
                binary_relevant_grade=binary_relevant_grade,
                deduplicated_by_loader=False,
            ),
            limitations=str(payload.get("limitations", "")).strip(),
        )
        converted = SearchEvaluationBenchmark(metadata=metadata, queries=tuple(queries))
    except ValidationError as exc:
        msg = f"invalid legacy lexical benchmark metadata or queries: {exc}"
        raise RetrievalError(msg) from exc
    validate_search_benchmark_integrity(converted)
    return converted


def convert_lexical_benchmark_path_to_search(
    path: Path,
    *,
    binary_relevant_grade: int = DEFAULT_LEGACY_BINARY_RELEVANT_GRADE,
    use_lexical_loader: bool = True,
) -> SearchEvaluationBenchmark:
    """Load legacy lexical JSON and convert to SearchEvaluationBenchmark."""
    resolved = Path(path)
    if use_lexical_loader:
        loaded = load_lexical_retrieval_benchmark(resolved)
        return convert_lexical_retrieval_benchmark_to_search(
            loaded,
            binary_relevant_grade=binary_relevant_grade,
        )
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        msg = f"legacy lexical benchmark is not valid JSON: {resolved}"
        raise RetrievalError(msg) from exc
    if not isinstance(payload, dict):
        msg = "legacy lexical benchmark must be a JSON object"
        raise RetrievalError(msg)
    return convert_lexical_benchmark_payload_to_search(
        payload,
        binary_relevant_grade=binary_relevant_grade,
    )


def lexical_evaluation_query_to_search_query(
    query: LexicalEvaluationQuery,
    *,
    binary_relevant_grade: int = DEFAULT_LEGACY_BINARY_RELEVANT_GRADE,
) -> SearchEvaluationQuery:
    return lexical_query_to_search_evaluation_query(
        query_id=query.query_id,
        query_text=query.query_text,
        category=query.category,
        relevant_product_ids=query.relevant_product_ids,
        binary_relevant_grade=binary_relevant_grade,
    )


__all__ = [
    "convert_lexical_benchmark_path_to_search",
    "convert_lexical_benchmark_payload_to_search",
    "convert_lexical_retrieval_benchmark_to_search",
    "lexical_evaluation_query_to_search_query",
]
