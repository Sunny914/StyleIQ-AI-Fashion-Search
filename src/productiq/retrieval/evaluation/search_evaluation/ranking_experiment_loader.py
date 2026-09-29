"""Load and validate ranking experiment inputs (Phase 12.7)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from productiq.exceptions.base import RetrievalError
from productiq.ranking.product_context import RankingProductContext
from productiq.ranking.product_context_provider import InMemoryRankingProductContextProvider
from productiq.representation.builder import build_product_representation
from productiq.representation.dataset import PARQUET_ENGINE
from productiq.representation.dataset_schema import REPRESENTATION_DATASET_COLUMN_ORDER
from productiq.representation.filtering import build_filtering_representation_from_canonical
from productiq.retrieval.contracts import RetrievalCandidate, RetrievalMethod, Retriever
from productiq.retrieval.evaluation.search_evaluation.baseline_artifact import (
    load_baseline_run_artifact,
    validate_baseline_run_artifact,
)
from productiq.retrieval.evaluation.search_evaluation.baseline_schema import (
    SEARCH_BASELINE_RRF_VARIANT_NAME,
)
from productiq.retrieval.evaluation.search_evaluation.benchmark_schema import (
    SearchEvaluationBenchmark,
)
from productiq.retrieval.evaluation.search_evaluation.ranking_experiment_schema import (
    SearchCandidatePoolConfiguration,
    SearchQueryCandidateSet,
    SearchRankingCandidatePool,
    SearchRetrievalProvenanceRecord,
)


def _retrieval_candidates_from_product_ids(
    product_ids: tuple[str, ...],
) -> tuple[RetrievalCandidate, ...]:
    """Rebuild retrieval metadata for a fixed ID list (retrieval order preserved)."""
    rows: list[RetrievalCandidate] = []
    for index, product_id in enumerate(product_ids, start=1):
        rank_score = float(len(product_ids) - index + 1)
        rows.append(
            RetrievalCandidate(
                product_id=product_id,
                score=rank_score,
                method=RetrievalMethod.HYBRID,
                retrieval_methods=(RetrievalMethod.BM25, RetrievalMethod.VECTOR),
                fusion_score=rank_score,
                bm25_rank=index,
                vector_rank=index,
            )
        )
    return tuple(rows)


def candidate_set_from_product_ids(
    *,
    query_id: str,
    product_ids: tuple[str, ...],
    candidate_provenance: str,
    include_retrieval_candidates: bool = True,
) -> SearchQueryCandidateSet:
    candidates = (
        _retrieval_candidates_from_product_ids(product_ids) if include_retrieval_candidates else ()
    )
    return SearchQueryCandidateSet(
        query_id=query_id,
        candidate_product_ids=product_ids,
        candidates=candidates,
        candidate_provenance=candidate_provenance,
    )


def generate_candidate_pool_from_retriever(
    benchmark: SearchEvaluationBenchmark,
    retriever: Retriever,
    *,
    candidate_pool_top_k: int,
    retrieval_provenance: SearchRetrievalProvenanceRecord,
    require_non_empty: bool = True,
) -> SearchRankingCandidatePool:
    """Generate a fixed candidate pool by retrieving once per benchmark query."""
    from productiq.representation.query_contract import build_query_representation
    from productiq.retrieval.contracts import RetrievalRequest
    from productiq.retrieval.evaluation.search_evaluation.metrics import (
        validate_search_ranked_product_ids,
    )

    query_sets: list[SearchQueryCandidateSet] = []
    for query in sorted(benchmark.queries, key=lambda row: row.query_id):
        response = retriever.retrieve(
            RetrievalRequest(
                query=build_query_representation(query.query_text),
                top_k=candidate_pool_top_k,
            )
        )
        product_ids = validate_search_ranked_product_ids(
            tuple(candidate.product_id for candidate in response.candidates)
        )
        if require_non_empty and not product_ids:
            msg = f"retriever returned empty candidate pool for query {query.query_id!r}"
            raise RetrievalError(msg)
        query_sets.append(
            SearchQueryCandidateSet(
                query_id=query.query_id,
                candidate_product_ids=product_ids,
                candidates=tuple(response.candidates),
                candidate_provenance="live_retriever_execution",
            )
        )
    return SearchRankingCandidatePool(
        benchmark_name=benchmark.metadata.benchmark_name,
        benchmark_version=benchmark.metadata.benchmark_version,
        candidate_pool_configuration=SearchCandidatePoolConfiguration(
            candidate_pool_top_k=candidate_pool_top_k,
            require_non_empty_candidates=require_non_empty,
        ),
        retrieval_provenance=retrieval_provenance,
        query_candidate_sets=tuple(query_sets),
    )


def candidate_pool_from_rrf_baseline_artifact(
    benchmark: SearchEvaluationBenchmark,
    artifact_path: Path,
    *,
    candidate_pool_top_k: int,
    retrieval_variant_version: str = "1.0.0",
) -> SearchRankingCandidatePool:
    """Build a fixed pool from Phase 12.5 RRF baseline per-query ranked IDs."""
    resolved = Path(artifact_path)
    payload = load_baseline_run_artifact(resolved)
    validate_baseline_run_artifact(payload)
    if payload.get("variant_name") != SEARCH_BASELINE_RRF_VARIANT_NAME:
        msg = f"expected RRF baseline artifact, got {payload.get('variant_name')!r}"
        raise RetrievalError(msg)
    if (
        payload.get("benchmark_name") != benchmark.metadata.benchmark_name
        or payload.get("benchmark_version") != benchmark.metadata.benchmark_version
    ):
        msg = "RRF baseline artifact benchmark identity does not match search benchmark"
        raise RetrievalError(msg)
    evaluation_result = payload.get("evaluation_result")
    if not isinstance(evaluation_result, dict):
        msg = "RRF baseline artifact missing evaluation_result"
        raise RetrievalError(msg)
    per_query = evaluation_result.get("per_query")
    if not isinstance(per_query, list):
        msg = "RRF baseline evaluation_result.per_query must be a list"
        raise RetrievalError(msg)
    expected_ids = {row.query_id for row in benchmark.queries}
    rows_by_id: dict[str, tuple[str, ...]] = {}
    for raw in per_query:
        if not isinstance(raw, dict):
            continue
        query_id = str(raw.get("query_id", ""))
        ranked = raw.get("ranked_product_ids")
        if not query_id or not isinstance(ranked, list):
            msg = f"invalid per_query row in RRF baseline artifact for {query_id!r}"
            raise RetrievalError(msg)
        ids = tuple(str(value) for value in ranked[:candidate_pool_top_k])
        rows_by_id[query_id] = ids
    missing = expected_ids - rows_by_id.keys()
    if missing:
        msg = f"RRF baseline artifact missing queries: {sorted(missing)[:5]}"
        raise RetrievalError(msg)
    extra = rows_by_id.keys() - expected_ids
    if extra:
        msg = f"RRF baseline artifact has unexpected query ids: {sorted(extra)[:5]}"
        raise RetrievalError(msg)
    provenance = SearchRetrievalProvenanceRecord(
        retrieval_variant_name=SEARCH_BASELINE_RRF_VARIANT_NAME,
        retrieval_variant_version=retrieval_variant_version,
        description="Phase 12.5 RRF baseline ranked_product_ids candidate pool.",
    )
    query_sets = tuple(
        candidate_set_from_product_ids(
            query_id=query_id,
            product_ids=rows_by_id[query_id],
            candidate_provenance="phase_12_5_rrf_baseline_run",
        )
        for query_id in sorted(rows_by_id.keys())
    )
    return SearchRankingCandidatePool(
        benchmark_name=benchmark.metadata.benchmark_name,
        benchmark_version=benchmark.metadata.benchmark_version,
        candidate_pool_configuration=SearchCandidatePoolConfiguration(
            candidate_pool_top_k=candidate_pool_top_k,
            require_non_empty_candidates=True,
        ),
        retrieval_provenance=provenance,
        query_candidate_sets=query_sets,
    )


def validate_candidate_pool_matches_definition(
    pool: SearchRankingCandidatePool,
    *,
    benchmark_name: str,
    benchmark_version: str,
    candidate_pool_configuration: SearchCandidatePoolConfiguration,
    retrieval_provenance: SearchRetrievalProvenanceRecord,
) -> None:
    if pool.benchmark_name != benchmark_name or pool.benchmark_version != benchmark_version:
        msg = "candidate pool benchmark identity does not match experiment definition"
        raise RetrievalError(msg)
    if pool.candidate_pool_configuration != candidate_pool_configuration:
        msg = "candidate pool configuration does not match experiment definition"
        raise RetrievalError(msg)
    if pool.retrieval_provenance != retrieval_provenance:
        msg = "candidate pool retrieval provenance does not match experiment definition"
        raise RetrievalError(msg)


def load_ranking_contexts_from_parquet(
    product_ids: tuple[str, ...],
    parquet_path: Path,
) -> InMemoryRankingProductContextProvider:
    """Load RankingProductContext rows for candidate IDs from the catalog parquet."""
    import pandas as pd

    resolved = Path(parquet_path)
    if not resolved.is_file():
        msg = f"catalog parquet not found: {resolved}"
        raise RetrievalError(msg)
    if not product_ids:
        return InMemoryRankingProductContextProvider({})
    unique_ids = tuple(dict.fromkeys(product_ids))
    frame = pd.read_parquet(
        resolved, engine=PARQUET_ENGINE, columns=list(REPRESENTATION_DATASET_COLUMN_ORDER)
    )
    filtered = frame[frame["product_id"].isin(unique_ids)]
    loaded: dict[str, RankingProductContext] = {}
    for _, row in filtered.iterrows():
        record = cast(dict[str, Any], row.to_dict())
        product = build_product_representation(record)
        filtering = build_filtering_representation_from_canonical(record)
        product_id = str(record["product_id"])
        loaded[product_id] = RankingProductContext(
            product_id=product_id,
            product=product,
            filtering=filtering,
        )
    missing = set(unique_ids) - loaded.keys()
    if missing:
        sample = sorted(missing)[:5]
        msg = f"missing catalog rows for candidate product_ids: {sample}"
        raise RetrievalError(msg)
    return InMemoryRankingProductContextProvider(loaded)


def load_ranking_experiment_artifact(path: Path) -> dict[str, object]:
    resolved = Path(path)
    if not resolved.is_file():
        msg = f"ranking experiment artifact not found: {resolved}"
        raise RetrievalError(msg)
    payload = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        msg = "ranking experiment artifact must be a JSON object"
        raise RetrievalError(msg)
    return payload


__all__ = [
    "candidate_pool_from_rrf_baseline_artifact",
    "candidate_set_from_product_ids",
    "generate_candidate_pool_from_retriever",
    "load_ranking_contexts_from_parquet",
    "load_ranking_experiment_artifact",
    "validate_candidate_pool_matches_definition",
]
