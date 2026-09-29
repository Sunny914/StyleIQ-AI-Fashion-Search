"""Tests for Phase 12.10 search evaluation reporting."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from productiq.exceptions.base import RetrievalError
from productiq.retrieval.evaluation.search_evaluation.reporting import (
    render_search_evaluation_report_markdown,
    run_default_search_evaluation_report,
    run_search_evaluation_report,
)
from productiq.retrieval.evaluation.search_evaluation.reporting.report_artifact import (
    build_search_evaluation_report_artifact_dict,
    validate_search_evaluation_report_artifact,
)
from productiq.retrieval.evaluation.search_evaluation.reporting.report_builder import (
    build_search_evaluation_report,
)
from productiq.retrieval.evaluation.search_evaluation.reporting.report_loader import (
    load_search_evaluation_report_sources,
)
from productiq.retrieval.evaluation.search_evaluation.reporting.report_schema import (
    SEARCH_EVALUATION_REPORT_FILENAME,
    SearchEvaluationReport,
    SearchEvaluationReportMetadata,
)
from productiq.retrieval.evaluation.search_evaluation.reporting.report_validation import (
    validate_report_sources,
)
from productiq.retrieval.evaluation.search_evaluation.reporting.reproducibility import (
    BM25_SCOPED_INDEX_MODE,
)
from productiq.retrieval.evaluation.search_evaluation.request_schema import (
    SearchMetricConfiguration,
)


def _repo_root() -> Path:
    return Path(".")


@pytest.fixture(scope="module")
def canonical_sources():
    root = _repo_root()
    if not (
        root / "resources/evaluation/productiq_search_benchmark_v1_baseline_bm25_run.json"
    ).is_file():
        pytest.skip("Phase 12.5 artifacts missing")
    return load_search_evaluation_report_sources(root)


class TestReportConstruction:
    def test_valid_report_construction(self, canonical_sources: object) -> None:
        report = build_search_evaluation_report(canonical_sources)
        assert report.variant_summaries
        assert report.reproducibility.source_artifacts

    def test_immutable_contract(self, canonical_sources: object) -> None:
        report = build_search_evaluation_report(canonical_sources)
        with pytest.raises((ValidationError, TypeError, AttributeError)):
            report.metadata.report_name = "other"  # type: ignore[misc]

    def test_extra_field_rejection(self) -> None:
        with pytest.raises(ValidationError):
            SearchEvaluationReportMetadata(report_name="x", extra_field="nope")  # type: ignore[call-arg]


class TestDeterminism:
    def test_deterministic_serialization(self, canonical_sources: object) -> None:
        first = build_search_evaluation_report(canonical_sources)
        second = build_search_evaluation_report(canonical_sources)
        assert json.dumps(first.model_dump(mode="json"), sort_keys=True) == json.dumps(
            second.model_dump(mode="json"),
            sort_keys=True,
        )

    def test_deterministic_checksum(self, canonical_sources: object) -> None:
        first = build_search_evaluation_report_artifact_dict(
            build_search_evaluation_report(canonical_sources)
        )
        second = build_search_evaluation_report_artifact_dict(
            build_search_evaluation_report(canonical_sources)
        )
        assert first["deterministic_checksum_sha256"] == second["deterministic_checksum_sha256"]
        validate_search_evaluation_report_artifact(first)

    def test_canonical_regeneration_twice(self) -> None:
        root = _repo_root()
        if not (
            root / "resources/evaluation/productiq_search_benchmark_v1_baseline_bm25_run.json"
        ).is_file():
            pytest.skip("Phase 12.5 artifacts missing")
        run_default_search_evaluation_report(root)
        path = root / "resources/evaluation" / SEARCH_EVALUATION_REPORT_FILENAME
        first = json.loads(path.read_text(encoding="utf-8"))
        run_default_search_evaluation_report(root)
        second = json.loads(path.read_text(encoding="utf-8"))
        assert first == second


class TestCompatibilityValidation:
    def test_benchmark_mismatch(self, canonical_sources: object) -> None:
        bad_benchmark = canonical_sources.benchmark.model_copy(
            update={
                "metadata": canonical_sources.benchmark.metadata.model_copy(
                    update={"benchmark_version": "9.9.9"}
                )
            }
        )
        sources = type(canonical_sources)(
            repo_root=canonical_sources.repo_root,
            benchmark=bad_benchmark,
            benchmark_path=canonical_sources.benchmark_path,
            benchmark_payload=canonical_sources.benchmark_payload,
            baselines=canonical_sources.baselines,
            baseline_experiment=canonical_sources.baseline_experiment,
            baseline_experiment_payload=canonical_sources.baseline_experiment_payload,
            ranking_experiment=canonical_sources.ranking_experiment,
            ranking_experiment_payload=canonical_sources.ranking_experiment_payload,
            failure_analysis=canonical_sources.failure_analysis,
            failure_analysis_payload=canonical_sources.failure_analysis_payload,
            statistical_analysis=canonical_sources.statistical_analysis,
            statistical_analysis_payload=canonical_sources.statistical_analysis_payload,
        )
        with pytest.raises(RetrievalError, match="benchmark identity"):
            validate_report_sources(sources)

    def test_metric_configuration_mismatch(self, canonical_sources: object) -> None:
        bundle = canonical_sources.baselines[0]
        bad_result = bundle.evaluation_result.model_copy(
            update={
                "lineage": bundle.evaluation_result.lineage.model_copy(
                    update={
                        "metric_configuration": SearchMetricConfiguration(
                            k_values=(1,),
                            evaluation_top_k=10,
                            execution_top_k=10,
                            min_relevant_grade=2,
                            compute_ndcg=False,
                        )
                    }
                )
            }
        )
        bad_bundle = type(bundle)(
            artifact_path=bundle.artifact_path,
            payload=bundle.payload,
            evaluation_result=bad_result,
        )
        sources = type(canonical_sources)(
            repo_root=canonical_sources.repo_root,
            benchmark=canonical_sources.benchmark,
            benchmark_path=canonical_sources.benchmark_path,
            benchmark_payload=canonical_sources.benchmark_payload,
            baselines=(bad_bundle, *canonical_sources.baselines[1:]),
            baseline_experiment=canonical_sources.baseline_experiment,
            baseline_experiment_payload=canonical_sources.baseline_experiment_payload,
            ranking_experiment=canonical_sources.ranking_experiment,
            ranking_experiment_payload=canonical_sources.ranking_experiment_payload,
            failure_analysis=canonical_sources.failure_analysis,
            failure_analysis_payload=canonical_sources.failure_analysis_payload,
            statistical_analysis=canonical_sources.statistical_analysis,
            statistical_analysis_payload=canonical_sources.statistical_analysis_payload,
        )
        with pytest.raises(RetrievalError, match="metric_configuration"):
            validate_report_sources(sources)

    def test_incompatible_experiment_schema(self, canonical_sources: object) -> None:
        if canonical_sources.baseline_experiment_payload is None:
            pytest.skip("12.6 artifact missing")
        bad_payload = dict(canonical_sources.baseline_experiment_payload)
        bad_payload["artifact_schema_version"] = "0.0.0"
        sources = type(canonical_sources)(
            repo_root=canonical_sources.repo_root,
            benchmark=canonical_sources.benchmark,
            benchmark_path=canonical_sources.benchmark_path,
            benchmark_payload=canonical_sources.benchmark_payload,
            baselines=canonical_sources.baselines,
            baseline_experiment=canonical_sources.baseline_experiment,
            baseline_experiment_payload=bad_payload,
            ranking_experiment=canonical_sources.ranking_experiment,
            ranking_experiment_payload=canonical_sources.ranking_experiment_payload,
            failure_analysis=canonical_sources.failure_analysis,
            failure_analysis_payload=canonical_sources.failure_analysis_payload,
            statistical_analysis=canonical_sources.statistical_analysis,
            statistical_analysis_payload=canonical_sources.statistical_analysis_payload,
        )
        with pytest.raises(RetrievalError, match="12.6"):
            validate_report_sources(sources)

    def test_malformed_statistical_artifact(self, tmp_path: Path) -> None:
        path = tmp_path / "bad_stat.json"
        path.write_text('{"artifact_schema_version":"12.9.0"}', encoding="utf-8")
        payload = json.loads(path.read_text(encoding="utf-8"))
        with pytest.raises(RetrievalError):
            from productiq.retrieval.evaluation.search_evaluation.statistical_artifact import (
                validate_search_statistical_analysis_artifact,
            )

            validate_search_statistical_analysis_artifact(payload)

    def test_malformed_failure_artifact(self, tmp_path: Path) -> None:
        path = tmp_path / "bad_fail.json"
        path.write_text('{"artifact_schema_version":"12.8.0"}', encoding="utf-8")
        payload = json.loads(path.read_text(encoding="utf-8"))
        with pytest.raises(RetrievalError):
            from productiq.retrieval.evaluation.search_evaluation.failure_analysis_artifact import (
                validate_search_failure_analysis_artifact,
            )

            validate_search_failure_analysis_artifact(payload)


class TestMissingArtifacts:
    def test_missing_baseline_raises(self, tmp_path: Path) -> None:
        with pytest.raises(RetrievalError, match="missing"):
            load_search_evaluation_report_sources(tmp_path)


class TestReproducibilityManifest:
    def test_manifest_correctness(self, canonical_sources: object) -> None:
        report = build_search_evaluation_report(canonical_sources)
        manifest = report.reproducibility
        assert manifest.benchmark_name == report.benchmark.benchmark_name
        assert manifest.metric_configuration == report.configuration.metric_configuration
        assert (
            manifest.statistical_bootstrap_seed is not None or report.statistical_analysis is None
        )

    def test_scoped_bm25_mode_preserved(self, canonical_sources: object) -> None:
        report = build_search_evaluation_report(canonical_sources)
        modes = {mode for _name, mode in report.reproducibility.retrieval_index_modes if mode}
        assert BM25_SCOPED_INDEX_MODE in modes or any(
            BM25_SCOPED_INDEX_MODE in item for item in report.limitations
        )

    def test_ltr_reproducibility_limitation_preserved(self, canonical_sources: object) -> None:
        report = build_search_evaluation_report(canonical_sources)
        text = "\n".join(report.limitations)
        assert "ranking_ltr_reference_v10_7_0" in text or "LTR" in text


class TestMarkdownRenderer:
    def test_markdown_rendering_determinism(self, canonical_sources: object) -> None:
        report = build_search_evaluation_report(canonical_sources)
        first = render_search_evaluation_report_markdown(report)
        second = render_search_evaluation_report_markdown(report)
        assert first == second
        assert "# ProductIQ Search Evaluation Report" in first


class TestPolicyFields:
    def test_no_winner_fields_in_schema(self) -> None:
        forbidden = {"winner", "recommended", "promotion"}
        for name in SearchEvaluationReport.model_fields:
            assert name.lower() not in forbidden


class TestIntegration:
    def test_run_search_evaluation_report(self) -> None:
        root = _repo_root()
        if not (
            root / "resources/evaluation/productiq_search_benchmark_v1_baseline_bm25_run.json"
        ).is_file():
            pytest.skip("Phase 12.5 artifacts missing")
        report = run_search_evaluation_report(root)
        assert report.statistical_analysis is None or report.statistical_analysis.comparisons
        assert len(report.reproducibility.source_artifacts) >= 4
