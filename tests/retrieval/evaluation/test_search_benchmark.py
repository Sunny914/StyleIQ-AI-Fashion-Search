"""Tests for Phase 12.2 search benchmark artifact loading and legacy adaptation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from productiq.exceptions import RetrievalError
from productiq.retrieval.evaluation.dataset import load_lexical_retrieval_benchmark
from productiq.retrieval.evaluation.schema import LEXICAL_RETRIEVAL_BENCHMARK_FILENAME
from productiq.retrieval.evaluation.search_evaluation import (
    DEFAULT_LEGACY_BINARY_RELEVANT_GRADE,
    LEGACY_LEXICAL_BENCHMARK_NAME,
    SEARCH_BENCHMARK_ARTIFACT_SCHEMA_VERSION,
    SEARCH_BENCHMARK_FILENAME,
    SEARCH_BENCHMARK_NAME,
    SEARCH_BENCHMARK_VERSION,
    SearchEvaluationBenchmark,
    SearchEvaluationBenchmarkMetadata,
    SearchEvaluationQuery,
    SearchEvaluationRequest,
    SearchEvaluationVariant,
    SearchRelevanceJudgment,
    build_search_evaluation_request,
    catalog_provenance_from_benchmark,
    convert_lexical_benchmark_path_to_search,
    convert_lexical_benchmark_payload_to_search,
    convert_lexical_retrieval_benchmark_to_search,
    load_search_evaluation_benchmark,
    sort_benchmark_for_stable_serialization,
    stable_benchmark_artifact_dict,
    summarize_search_benchmark_integrity,
    validate_search_benchmark_integrity,
)
from productiq.retrieval.evaluation.search_evaluation.benchmark_loader import (
    SearchBenchmarkArtifactFile,
)


def _minimal_metadata(**overrides: object) -> SearchEvaluationBenchmarkMetadata:
    base: dict[str, object] = {
        "benchmark_name": "test_benchmark",
        "benchmark_version": "0.0.1",
        "methodology": "test methodology",
        "labeling_methodology": "test labeling",
        "limitations": "test limitations",
    }
    base.update(overrides)
    return SearchEvaluationBenchmarkMetadata(**base)


def _single_query_benchmark() -> SearchEvaluationBenchmark:
    query = SearchEvaluationQuery(
        query_id="q1",
        query_text="test query",
        query_category="test",
        relevance_judgments=(SearchRelevanceJudgment(product_id="P1", grade=2),),
    )
    return SearchEvaluationBenchmark(metadata=_minimal_metadata(), queries=(query,))


class TestCanonicalBenchmarkArtifact:
    def test_loads_repository_benchmark(self) -> None:
        path = Path("resources/evaluation") / SEARCH_BENCHMARK_FILENAME
        benchmark = load_search_evaluation_benchmark(path)
        assert benchmark.benchmark_name == SEARCH_BENCHMARK_NAME
        assert benchmark.benchmark_version == SEARCH_BENCHMARK_VERSION
        summary = summarize_search_benchmark_integrity(benchmark)
        assert summary.query_count == 10
        assert summary.judgment_count == 44
        assert summary.grade_distribution == ((2, 44),)

    def test_builds_search_evaluation_request(self) -> None:
        path = Path("resources/evaluation") / SEARCH_BENCHMARK_FILENAME
        benchmark = load_search_evaluation_benchmark(path)
        variant = SearchEvaluationVariant(variant_name="bm25", variant_version="1.0.0")
        request = build_search_evaluation_request(benchmark, variant)
        assert isinstance(request, SearchEvaluationRequest)
        assert request.benchmark.benchmark_name == SEARCH_BENCHMARK_NAME
        assert request.metric_configuration.min_relevant_grade == 2

    def test_catalog_provenance_without_database(self) -> None:
        path = Path("resources/evaluation") / SEARCH_BENCHMARK_FILENAME
        benchmark = load_search_evaluation_benchmark(path)
        provenance = catalog_provenance_from_benchmark(benchmark)
        assert provenance.catalog_artifact is not None
        assert provenance.source_representation_checksum is not None
        assert "product_representations" in provenance.catalog_artifact

    def test_deterministic_reload(self) -> None:
        path = Path("resources/evaluation") / SEARCH_BENCHMARK_FILENAME
        first = load_search_evaluation_benchmark(path)
        second = load_search_evaluation_benchmark(path)
        assert stable_benchmark_artifact_dict(first) == stable_benchmark_artifact_dict(second)


class TestBenchmarkLoaderValidation:
    def test_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(RetrievalError, match="not found"):
            load_search_evaluation_benchmark(tmp_path / "missing.json")

    def test_invalid_schema_version(self, tmp_path: Path) -> None:
        body = _single_query_benchmark()
        payload = {
            "artifact_schema_version": "99.0.0",
            "metadata": body.metadata.model_dump(mode="json"),
            "queries": [q.model_dump(mode="json") for q in body.queries],
        }
        path = tmp_path / "bad_schema.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(RetrievalError, match="artifact_schema_version"):
            load_search_evaluation_benchmark(path)

    def test_missing_metadata_name(self) -> None:
        with pytest.raises(ValidationError):
            SearchEvaluationBenchmarkMetadata(
                benchmark_name="",
                benchmark_version="1.0.0",
                methodology="m",
                labeling_methodology="l",
                limitations="x",
            )

    def test_missing_metadata_version(self) -> None:
        with pytest.raises(ValidationError):
            SearchEvaluationBenchmarkMetadata(
                benchmark_name="name",
                benchmark_version="",
                methodology="m",
                labeling_methodology="l",
                limitations="x",
            )


class TestBenchmarkQueryValidation:
    def test_empty_benchmark_queries(self) -> None:
        with pytest.raises(ValidationError, match="at least one query"):
            SearchEvaluationBenchmark(metadata=_minimal_metadata(), queries=())

    def test_duplicate_query_id(self) -> None:
        q = SearchEvaluationQuery(
            query_id="dup",
            query_text="a",
            relevance_judgments=(SearchRelevanceJudgment(product_id="P1", grade=2),),
        )
        with pytest.raises(ValidationError, match="unique"):
            SearchEvaluationBenchmark(metadata=_minimal_metadata(), queries=(q, q))

    def test_empty_query_id(self) -> None:
        with pytest.raises(ValidationError):
            SearchEvaluationQuery(
                query_id="  ",
                query_text="text",
                relevance_judgments=(SearchRelevanceJudgment(product_id="P1", grade=2),),
            )

    def test_empty_query_text(self) -> None:
        with pytest.raises(ValidationError):
            SearchEvaluationQuery(
                query_id="q1",
                query_text="",
                relevance_judgments=(SearchRelevanceJudgment(product_id="P1", grade=2),),
            )

    def test_empty_judgments(self) -> None:
        with pytest.raises(ValidationError):
            SearchEvaluationQuery(
                query_id="q1",
                query_text="text",
                relevance_judgments=(),
            )


class TestJudgmentValidation:
    def test_empty_product_id(self) -> None:
        with pytest.raises(ValidationError):
            SearchRelevanceJudgment(product_id="  ", grade=2)

    def test_invalid_grade(self) -> None:
        with pytest.raises(ValidationError):
            SearchRelevanceJudgment(product_id="P1", grade=4)

    def test_duplicate_product_within_query(self) -> None:
        with pytest.raises(ValidationError, match="duplicate product_id"):
            SearchEvaluationQuery(
                query_id="q1",
                query_text="text",
                relevance_judgments=(
                    SearchRelevanceJudgment(product_id="P1", grade=2),
                    SearchRelevanceJudgment(product_id="P1", grade=3),
                ),
            )


class TestLegacyAdapter:
    def test_loaded_lexical_matches_counts(self) -> None:
        lexical_path = Path("resources/evaluation") / LEXICAL_RETRIEVAL_BENCHMARK_FILENAME
        lexical = load_lexical_retrieval_benchmark(lexical_path)
        assert lexical.benchmark_name == LEGACY_LEXICAL_BENCHMARK_NAME
        converted = convert_lexical_retrieval_benchmark_to_search(lexical)
        summary = summarize_search_benchmark_integrity(converted)
        assert summary.query_count == 10
        assert summary.judgment_count == 44
        assert converted.metadata.benchmark_name == LEGACY_LEXICAL_BENCHMARK_NAME

    def test_payload_path_matches_loader_path_for_current_artifact(self) -> None:
        lexical_path = Path("resources/evaluation") / LEXICAL_RETRIEVAL_BENCHMARK_FILENAME
        from_loader = convert_lexical_benchmark_path_to_search(
            lexical_path, use_lexical_loader=True
        )
        from_payload = convert_lexical_benchmark_path_to_search(
            lexical_path, use_lexical_loader=False
        )
        loader_sorted = sort_benchmark_for_stable_serialization(from_loader)
        payload_sorted = sort_benchmark_for_stable_serialization(from_payload)
        assert loader_sorted.queries == payload_sorted.queries
        assert from_loader.metadata.benchmark_name == from_payload.metadata.benchmark_name

    def test_canonical_matches_legacy_adapter_queries(self) -> None:
        lexical_path = Path("resources/evaluation") / LEXICAL_RETRIEVAL_BENCHMARK_FILENAME
        adapted = convert_lexical_benchmark_path_to_search(lexical_path)
        canonical = load_search_evaluation_benchmark(
            Path("resources/evaluation") / SEARCH_BENCHMARK_FILENAME
        )
        adapted_sorted = sort_benchmark_for_stable_serialization(adapted)
        canonical_sorted = sort_benchmark_for_stable_serialization(canonical)
        assert [q.query_id for q in adapted_sorted.queries] == [
            q.query_id for q in canonical_sorted.queries
        ]
        for left, right in zip(adapted_sorted.queries, canonical_sorted.queries, strict=True):
            assert left.query_text == right.query_text
            assert left.relevance_judgments == right.relevance_judgments

    def test_payload_rejects_duplicate_product_in_query(self) -> None:
        payload = {
            "benchmark_name": "legacy",
            "benchmark_version": "1.0.0",
            "catalog_artifact": "resources/processed/product_representations.parquet",
            "methodology": "m",
            "limitations": "l",
            "queries": [
                {
                    "query_id": "q1",
                    "query_text": "t",
                    "category": "c",
                    "relevant_product_ids": ["P1", "P1"],
                }
            ],
        }
        with pytest.raises(RetrievalError):
            convert_lexical_benchmark_payload_to_search(payload)

    def test_default_binary_grade(self) -> None:
        assert DEFAULT_LEGACY_BINARY_RELEVANT_GRADE == 2


class TestArtifactEnvelope:
    def test_supported_schema_version_constant(self) -> None:
        path = Path("resources/evaluation") / SEARCH_BENCHMARK_FILENAME
        raw = json.loads(path.read_text(encoding="utf-8"))
        assert raw["artifact_schema_version"] == SEARCH_BENCHMARK_ARTIFACT_SCHEMA_VERSION
        artifact = SearchBenchmarkArtifactFile.model_validate(raw)
        assert artifact.to_benchmark().benchmark_name == SEARCH_BENCHMARK_NAME

    def test_integrity_validator_runs(self) -> None:
        benchmark = _single_query_benchmark()
        validate_search_benchmark_integrity(benchmark)
