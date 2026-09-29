"""Tests for Phase 12.5 baseline search evaluation."""

from __future__ import annotations

from pathlib import Path

from productiq.retrieval.evaluation.search_evaluation import (
    MappingSearchEvaluationExecutor,
    SearchEvaluationBenchmark,
    SearchEvaluationBenchmarkMetadata,
    SearchEvaluationQuery,
    SearchEvaluationVariant,
    SearchRelevanceJudgment,
    build_search_evaluation_request,
)
from productiq.retrieval.evaluation.search_evaluation.baseline_artifact import (
    build_baseline_run_artifact,
    default_baseline_metric_configuration,
    load_baseline_run_artifact,
    validate_baseline_run_artifact,
    write_baseline_run_artifact,
)
from productiq.retrieval.evaluation.search_evaluation.baseline_evaluation import (
    baseline_run_artifact_path,
    evaluate_search_baseline,
    load_canonical_search_benchmark,
)
from productiq.retrieval.evaluation.search_evaluation.baseline_schema import (
    SEARCH_BASELINE_BM25_RUN_FILENAME,
    SEARCH_BASELINE_BM25_VARIANT_NAME,
)
from productiq.retrieval.evaluation.search_evaluation.baseline_variants import (
    bm25_retrieval_provenance,
    bm25_search_evaluation_variant,
)
from productiq.retrieval.evaluation.search_evaluation.runner import run_search_evaluation


def _mini_benchmark() -> SearchEvaluationBenchmark:
    return SearchEvaluationBenchmark(
        metadata=SearchEvaluationBenchmarkMetadata(
            benchmark_name="productiq_search_benchmark_v1",
            benchmark_version="1.0.0",
            methodology="test",
            labeling_methodology="test",
            limitations="test",
        ),
        queries=(
            SearchEvaluationQuery(
                query_id="q_a",
                query_text="alpha",
                relevance_judgments=(SearchRelevanceJudgment(product_id="P1", grade=2),),
            ),
            SearchEvaluationQuery(
                query_id="q_b",
                query_text="beta",
                relevance_judgments=(SearchRelevanceJudgment(product_id="P2", grade=2),),
            ),
        ),
    )


class TestBaselineVariantMetadata:
    def test_bm25_variant_uses_manifest_schema_version(self) -> None:
        manifest = {
            "schema_version": "1.0.0",
            "checksum": "abc123",
            "index_name": "bm25_lexical_index",
            "source_representation_checksum": "rep",
        }
        variant = bm25_search_evaluation_variant(index_mode="full_persisted_index", bm25_manifest=manifest)
        assert variant.variant_name == SEARCH_BASELINE_BM25_VARIANT_NAME
        assert variant.variant_version == "1.0.0"
        assert any("abc123" in label for label in variant.lineage_labels)


class TestBaselineArtifact:
    def test_roundtrip_write_validate(self, tmp_path: Path) -> None:
        benchmark = _mini_benchmark()
        variant = SearchEvaluationVariant(variant_name="toy", variant_version="0.0.1")
        config = default_baseline_metric_configuration()
        request = build_search_evaluation_request(benchmark, variant, metric_configuration=config)
        executor = MappingSearchEvaluationExecutor({"q_a": ("P1",), "q_b": ("X", "P2")})
        result = run_search_evaluation(request, executor)
        artifact = build_baseline_run_artifact(
            result,
            retrieval_provenance={"retrieval_mode": "toy"},
            runtime_metadata={"evaluation_duration_seconds": 0.01},
        )
        path = tmp_path / "artifact.json"
        write_baseline_run_artifact(path, artifact)
        loaded = load_baseline_run_artifact(path)
        validate_baseline_run_artifact(loaded)
        assert loaded["query_count"] == 2
        per_query = loaded["evaluation_result"]["per_query"]
        assert len(per_query) == 2
        assert "precision_at_k" in per_query[0]

    def test_deterministic_checksum_stable(self) -> None:
        benchmark = _mini_benchmark()
        variant = SearchEvaluationVariant(variant_name="toy", variant_version="0.0.1")
        request = build_search_evaluation_request(
            benchmark,
            variant,
            metric_configuration=default_baseline_metric_configuration(),
        )
        executor = MappingSearchEvaluationExecutor({"q_a": ("P1",), "q_b": ("P2",)})
        result = run_search_evaluation(request, executor)
        first = build_baseline_run_artifact(
            result,
            retrieval_provenance={"retrieval_mode": "toy"},
            runtime_metadata={"evaluation_duration_seconds": 1.0},
        )
        second = build_baseline_run_artifact(
            result,
            retrieval_provenance={"retrieval_mode": "toy"},
            runtime_metadata={"evaluation_duration_seconds": 99.0},
        )
        assert first["deterministic_checksum_sha256"] == second["deterministic_checksum_sha256"]


class TestBaselineEvaluationFlow:
    def test_evaluate_search_baseline_end_to_end(self) -> None:
        benchmark = _mini_benchmark()
        variant = SearchEvaluationVariant(variant_name="toy", variant_version="1.0.0")
        config = default_baseline_metric_configuration()
        request = build_search_evaluation_request(benchmark, variant, metric_configuration=config)
        executor = MappingSearchEvaluationExecutor({"q_a": (), "q_b": ("P2",)})
        result, artifact = evaluate_search_baseline(
            request,
            executor,
            retrieval_provenance=bm25_retrieval_provenance(
                index_mode="toy",
                bm25_manifest={"schema_version": "1.0.0", "checksum": "x"},
                index_path="resources/processed/bm25_lexical_index.pkl",
            ),
            runtime_metadata={},
        )
        assert result.aggregate.query_count == 2
        assert artifact["successful_query_count"] == 2
        assert artifact["execution_configuration"]["execution_top_k"] == config.execution_top_k
        assert result.lineage.metric_configuration.execution_top_k == config.execution_top_k

    def test_canonical_benchmark_from_repository(self) -> None:
        benchmark = load_canonical_search_benchmark(Path("."))
        assert len(benchmark.queries) == 10

    def test_artifact_path_convention(self) -> None:
        path = baseline_run_artifact_path(Path("/repo"), "bm25")
        assert path.name == SEARCH_BASELINE_BM25_RUN_FILENAME


class TestDefaultBaselineMetricConfiguration:
    def test_execution_and_evaluation_top_k_explicit(self) -> None:
        config = default_baseline_metric_configuration()
        assert config.execution_top_k == 50
        assert config.evaluation_top_k == 50
        assert config.min_relevant_grade == 2
        assert config.compute_ndcg is True
