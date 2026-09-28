"""Semantic retrieval evaluation orchestration (Phase 4.14)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.engine import Engine

from productiq.representation.query_contract import build_query_representation
from productiq.retrieval.contracts import RetrievalRequest, Retriever
from productiq.retrieval.evaluation.contracts import (
    AggregateMetricValues,
    LexicalRetrievalEvaluationResult,
    PerQueryMetricValues,
    QueryEvaluationResult,
)
from productiq.retrieval.evaluation.metrics import (
    count_relevant_in_prefix,
    macro_mean,
    mean_reciprocal_rank,
    normalize_relevant_product_ids,
    normalize_retrieved_product_ids,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
    validate_positive_k,
)
from productiq.retrieval.evaluation.schema import DEFAULT_EVALUATION_K_VALUES
from productiq.retrieval.evaluation.semantic_catalog_validation import (
    validate_benchmark_product_ids_in_catalog,
)
from productiq.retrieval.evaluation.semantic_dataset import SemanticRetrievalBenchmark


@dataclass(frozen=True)
class SemanticRetrievalEvaluationContext:
    """Lineage metadata recorded in semantic evaluation run artifacts."""

    embedding_model_id: str
    embedding_model_revision: str | None
    embedding_dimension: int
    similarity_metric: str
    retrieval_method: str
    source_embedding_artifact_checksum: str | None
    source_representation_checksum: str | None
    vector_index_name: str
    evaluation_timestamp_utc: str


@dataclass(frozen=True)
class SemanticRetrievalEvaluationOutput:
    """Evaluation result plus retrieval score details for analysis artifacts."""

    result: LexicalRetrievalEvaluationResult
    context: SemanticRetrievalEvaluationContext
    retrieved_details_by_query_id: dict[str, tuple[dict[str, Any], ...]]
    judged_relevant_by_query_id: dict[str, tuple[str, ...]]


class SemanticRetrievalEvaluator:
    """Evaluate ``SemanticRetriever`` on a semantic benchmark via the ``Retriever`` protocol."""

    def __init__(
        self,
        *,
        retrieval_top_k: int = 50,
        k_values: tuple[int, ...] = DEFAULT_EVALUATION_K_VALUES,
    ) -> None:
        validate_positive_k(retrieval_top_k)
        if not k_values:
            msg = "k_values must not be empty"
            raise ValueError(msg)
        for k in k_values:
            validate_positive_k(k)
        self._retrieval_top_k = retrieval_top_k
        self._k_values = tuple(sorted(set(k_values)))

    @property
    def retrieval_top_k(self) -> int:
        return self._retrieval_top_k

    @property
    def k_values(self) -> tuple[int, ...]:
        return self._k_values

    def validate_benchmark(self, benchmark: SemanticRetrievalBenchmark, engine: Engine) -> int:
        return validate_benchmark_product_ids_in_catalog(benchmark, engine)

    def evaluate(
        self,
        benchmark: SemanticRetrievalBenchmark,
        retriever: Retriever,
        *,
        engine: Engine | None = None,
        validate_catalog: bool = True,
        vector_index_name: str = "product_vector_index",
    ) -> SemanticRetrievalEvaluationOutput:
        if validate_catalog:
            if engine is None:
                msg = "engine is required when validate_catalog is True"
                raise ValueError(msg)
            self.validate_benchmark(benchmark, engine)

        per_query: list[QueryEvaluationResult] = []
        retrieved_details_by_query_id: dict[str, tuple[dict[str, Any], ...]] = {}
        judged_relevant_by_query_id: dict[str, tuple[str, ...]] = {}

        for evaluation_query in benchmark.queries:
            request = RetrievalRequest(
                query=build_query_representation(evaluation_query.query_text),
                top_k=self._retrieval_top_k,
            )
            response = retriever.retrieve(request)
            retrieved = normalize_retrieved_product_ids(
                tuple(candidate.product_id for candidate in response.candidates),
                max_count=self._retrieval_top_k,
            )
            relevant = normalize_relevant_product_ids(evaluation_query.relevant_product_ids)
            judged_relevant_by_query_id[evaluation_query.query_id] = evaluation_query.relevant_product_ids
            retrieved_details_by_query_id[evaluation_query.query_id] = tuple(
                {
                    "product_id": candidate.product_id,
                    "similarity_score": candidate.score,
                    "method": candidate.method.value,
                }
                for candidate in response.candidates
            )
            rr, first_rank = reciprocal_rank(retrieved, relevant)
            precision_map: dict[int, float] = {}
            recall_map: dict[int, float | None] = {}
            hits_map: dict[int, int] = {}
            for k in self._k_values:
                effective_k = min(k, self._retrieval_top_k)
                hits_map[k] = count_relevant_in_prefix(retrieved, relevant, k=effective_k)
                precision_map[k] = precision_at_k(retrieved, relevant, k=effective_k)
                recall_map[k] = recall_at_k(retrieved, relevant, k=effective_k)
            recall_eligible = len(relevant) > 0
            per_query.append(
                QueryEvaluationResult(
                    query_id=evaluation_query.query_id,
                    query_text=evaluation_query.query_text,
                    category=evaluation_query.category,
                    judged_relevant_count=len(relevant),
                    metrics=PerQueryMetricValues(
                        precision_at_k=precision_map,
                        recall_at_k=recall_map,
                        reciprocal_rank=rr,
                        recall_aggregate_eligible=recall_eligible,
                        retrieved_product_ids=retrieved,
                        relevant_hits_in_top_k=hits_map,
                        first_relevant_rank=first_rank,
                    ),
                    retrieval_candidate_count=response.candidate_count,
                )
            )

        aggregate = self._aggregate(per_query)
        result = LexicalRetrievalEvaluationResult(
            benchmark_name=benchmark.benchmark_name,
            benchmark_version=benchmark.benchmark_version,
            retrieval_top_k=self._retrieval_top_k,
            k_values=self._k_values,
            per_query=tuple(per_query),
            aggregate=aggregate,
        )
        context = SemanticRetrievalEvaluationContext(
            embedding_model_id=benchmark.embedding_model_id,
            embedding_model_revision=benchmark.embedding_model_revision,
            embedding_dimension=benchmark.embedding_dimension,
            similarity_metric=benchmark.similarity_metric,
            retrieval_method=benchmark.retrieval_method,
            source_embedding_artifact_checksum=benchmark.source_embedding_artifact_checksum,
            source_representation_checksum=benchmark.source_representation_checksum,
            vector_index_name=vector_index_name,
            evaluation_timestamp_utc=datetime.now(tz=UTC).isoformat(),
        )
        return SemanticRetrievalEvaluationOutput(
            result=result,
            context=context,
            retrieved_details_by_query_id=retrieved_details_by_query_id,
            judged_relevant_by_query_id=judged_relevant_by_query_id,
        )

    def _aggregate(self, per_query: list[QueryEvaluationResult]) -> AggregateMetricValues:
        mean_precision: dict[int, float] = {}
        mean_recall: dict[int, float] = {}
        for k in self._k_values:
            mean_precision[k] = macro_mean(
                tuple(result.metrics.precision_at_k[k] for result in per_query)
            )
            recall_values_list: list[float] = []
            for result in per_query:
                if not result.metrics.recall_aggregate_eligible:
                    continue
                recall_value = result.metrics.recall_at_k[k]
                if recall_value is None:
                    continue
                recall_values_list.append(recall_value)
            mean_recall[k] = macro_mean(recall_values_list) if recall_values_list else 0.0
        recall_aggregate_query_count = sum(
            1 for result in per_query if result.metrics.recall_aggregate_eligible
        )
        mrr = mean_reciprocal_rank(tuple(result.metrics.reciprocal_rank for result in per_query))
        return AggregateMetricValues(
            mean_precision_at_k=mean_precision,
            mean_recall_at_k=mean_recall,
            mrr=mrr,
            query_count=len(per_query),
            recall_aggregate_query_count=recall_aggregate_query_count,
            k_values=self._k_values,
        )


def build_per_query_analysis_rows(output: SemanticRetrievalEvaluationOutput) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for query_result in output.result.per_query:
        rows.append(
            {
                "query_id": query_result.query_id,
                "query_text": query_result.query_text,
                "category": query_result.category,
                "first_relevant_rank": query_result.metrics.first_relevant_rank,
                "judged_relevant_count": query_result.judged_relevant_count,
                "judged_relevant_product_ids": list(
                    output.judged_relevant_by_query_id.get(query_result.query_id, ())
                ),
                "retrieved_product_ids": list(query_result.metrics.retrieved_product_ids),
                "retrieved_details": list(
                    output.retrieved_details_by_query_id.get(query_result.query_id, ())
                ),
                "precision_at_k": query_result.metrics.precision_at_k,
                "recall_at_k": {
                    str(k): value for k, value in query_result.metrics.recall_at_k.items()
                },
                "reciprocal_rank": query_result.metrics.reciprocal_rank,
            }
        )
    return rows


__all__ = [
    "SemanticRetrievalEvaluationContext",
    "SemanticRetrievalEvaluationOutput",
    "SemanticRetrievalEvaluator",
    "build_per_query_analysis_rows",
]
