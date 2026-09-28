"""Tests for Phase 4.14 semantic retrieval evaluation."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from productiq.exceptions.base import LexicalRetrievalError
from productiq.retrieval.contracts import (
    RetrievalCandidate,
    RetrievalMethod,
    RetrievalRequest,
    RetrievalResponse,
)
from productiq.retrieval.evaluation.semantic_dataset import (
    SemanticRetrievalBenchmark,
    load_semantic_retrieval_benchmark,
)
from productiq.retrieval.evaluation.semantic_evaluator import (
    SemanticRetrievalEvaluator,
    build_per_query_analysis_rows,
)
from productiq.retrieval.evaluation.semantic_schema import (
    SEMANTIC_RETRIEVAL_BENCHMARK_RUN_FILENAME,
)

pytest_plugins = ["tests.database.conftest"]

INTEGRATION_ENV_VAR = "PRODUCTIQ_RUN_INTEGRATION_TESTS"
SEMANTIC_SMOKE_ENV_VAR = "PRODUCTIQ_SEMANTIC_RETRIEVAL_SMOKE"


class FakeSemanticRetriever:
    def __init__(self, ranking: dict[str, tuple[tuple[str, float], ...]]) -> None:
        self._ranking = ranking

    def retrieve(self, request: RetrievalRequest) -> RetrievalResponse:
        query_text = request.query.query_text.strip().lower()
        hits = self._ranking.get(query_text, ())
        top = hits[: request.top_k]
        candidates = tuple(
            RetrievalCandidate(
                product_id=pid,
                score=score,
                method=RetrievalMethod.VECTOR,
            )
            for pid, score in top
        )
        return RetrievalResponse(candidates=candidates)


def _tiny_semantic_benchmark() -> SemanticRetrievalBenchmark:
    from productiq.retrieval.evaluation.dataset import LexicalEvaluationQuery

    return SemanticRetrievalBenchmark(
        benchmark_name="test_semantic",
        benchmark_version="0.0.1",
        catalog_artifact="test.parquet",
        embedding_model_id="test/model",
        embedding_dimension=384,
        similarity_metric="cosine",
        retrieval_method="vector",
        relevance_policy="test policy",
        methodology="test",
        limitations="incomplete judgments (test)",
        queries=(
            LexicalEvaluationQuery(
                query_id="q1",
                query_text="alpha",
                category="test",
                relevant_product_ids=("A", "B"),
            ),
            LexicalEvaluationQuery(
                query_id="q2",
                query_text="beta",
                category="test",
                relevant_product_ids=("C",),
            ),
        ),
    )


def test_semantic_benchmark_json_loads() -> None:
    path = Path("resources/evaluation/semantic_retrieval_benchmark_v1.json")
    benchmark = load_semantic_retrieval_benchmark(path)
    assert len(benchmark.queries) == 10
    assert benchmark.benchmark_version == "1.0.0"
    assert benchmark.retrieval_method == "vector"
    assert benchmark.embedding_dimension == 384


def test_semantic_benchmark_rejects_wrong_retrieval_method() -> None:
    payload = json.loads(
        Path("resources/evaluation/semantic_retrieval_benchmark_v1.json").read_text(encoding="utf-8")
    )
    payload["retrieval_method"] = "bm25"
    with pytest.raises(ValidationError):
        SemanticRetrievalBenchmark.model_validate(payload)


def test_semantic_evaluator_with_fake_retriever() -> None:
    retriever = FakeSemanticRetriever(
        {
            "alpha": (("A", 0.9), ("X", 0.5), ("B", 0.4)),
            "beta": (("X", 0.3), ("Y", 0.2)),
        }
    )
    evaluator = SemanticRetrievalEvaluator(retrieval_top_k=10, k_values=(1, 3))
    output = evaluator.evaluate(_tiny_semantic_benchmark(), retriever, validate_catalog=False)
    result = output.result
    assert result.aggregate.query_count == 2
    q1 = next(row for row in result.per_query if row.query_id == "q1")
    assert q1.metrics.precision_at_k[1] == pytest.approx(1.0)
    assert q1.metrics.recall_at_k[3] == pytest.approx(1.0)
    assert q1.metrics.reciprocal_rank == pytest.approx(1.0)
    q2 = next(row for row in result.per_query if row.query_id == "q2")
    assert q2.metrics.reciprocal_rank == 0.0


def test_build_per_query_analysis_rows_includes_scores() -> None:
    retriever = FakeSemanticRetriever({"alpha": (("A", 0.88),)})
    evaluator = SemanticRetrievalEvaluator(retrieval_top_k=5, k_values=(1,))
    output = evaluator.evaluate(_tiny_semantic_benchmark(), retriever, validate_catalog=False)
    rows = build_per_query_analysis_rows(output)
    alpha = next(row for row in rows if row["query_id"] == "q1")
    assert alpha["judged_relevant_product_ids"] == ["A", "B"]
    assert alpha["retrieved_details"][0]["similarity_score"] == pytest.approx(0.88)


def test_run_artifact_schema_fields() -> None:
    path = Path("resources/evaluation") / SEMANTIC_RETRIEVAL_BENCHMARK_RUN_FILENAME
    if not path.is_file():
        pytest.skip("semantic run artifact not generated yet")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert "benchmark" in payload
    assert "retrieval" in payload
    assert "aggregate" in payload
    assert "per_query" in payload
    assert payload["benchmark"]["query_count"] == 10
    assert "incomplete_judgment_warning" in payload


def test_catalog_validation_fails_on_missing_product(integration_engine) -> None:
    if os.getenv(INTEGRATION_ENV_VAR) != "1":
        pytest.skip("integration DB not enabled")
    from productiq.retrieval.evaluation.dataset import LexicalEvaluationQuery

    benchmark = SemanticRetrievalBenchmark(
        benchmark_name="bad",
        benchmark_version="0.0.1",
        catalog_artifact="test.parquet",
        embedding_model_id="test/model",
        embedding_dimension=384,
        similarity_metric="cosine",
        retrieval_method="vector",
        relevance_policy="test",
        methodology="test",
        limitations="test",
        queries=(
            LexicalEvaluationQuery(
                query_id="bad",
                query_text="x",
                category="test",
                relevant_product_ids=("000000000000",),
            ),
        ),
    )
    evaluator = SemanticRetrievalEvaluator()
    with pytest.raises(LexicalRetrievalError, match="missing from products"):
        evaluator.validate_benchmark(benchmark, integration_engine)


@pytest.mark.integration
@pytest.mark.skipif(os.getenv(INTEGRATION_ENV_VAR) != "1", reason="Set PRODUCTIQ_RUN_INTEGRATION_TESTS=1")
@pytest.mark.skipif(
    os.getenv(SEMANTIC_SMOKE_ENV_VAR) != "1",
    reason=f"Set {SEMANTIC_SMOKE_ENV_VAR}=1 for semantic benchmark integration",
)
def test_semantic_benchmark_evaluation_integration(integration_engine) -> None:
    from productiq.database.vector_catalog import count_products_with_embeddings
    from productiq.retrieval.embedding_encoder import create_bge_small_en_v15_encoder
    from productiq.retrieval.semantic_retriever import create_semantic_retriever_from_engine

    if count_products_with_embeddings(integration_engine) < 1_000:
        pytest.skip("vector index not loaded")
    benchmark = load_semantic_retrieval_benchmark(
        Path("resources/evaluation/semantic_retrieval_benchmark_v1.json")
    )
    encoder = create_bge_small_en_v15_encoder(device="cpu", allow_cpu_fallback=True)
    retriever = create_semantic_retriever_from_engine(integration_engine, encoder)
    evaluator = SemanticRetrievalEvaluator(retrieval_top_k=50, k_values=(1, 5, 10, 20, 50))
    output = evaluator.evaluate(benchmark, retriever, engine=integration_engine)
    assert output.result.aggregate.query_count == len(benchmark.queries)
    assert 0.0 <= output.result.aggregate.mrr <= 1.0
