"""Tests for Phase 12.11 search evaluation hardening."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from productiq.exceptions.base import RetrievalError
from productiq.retrieval.evaluation.search_evaluation.baseline_schema import (
    SEARCH_BASELINE_BM25_RUN_FILENAME,
)
from productiq.retrieval.evaluation.search_evaluation.experiment_validation import (
    validate_shared_evaluation_envelope,
)
from productiq.retrieval.evaluation.search_evaluation.hardening import (
    ltr_artifact_status,
    run_search_evaluation_hardening_audit,
    validate_persisted_artifact_integrity,
    validate_report_generation_determinism,
    validate_search_evaluation_hardening_sources,
)
from productiq.retrieval.evaluation.search_evaluation.hardening.failure_modes import (
    FORBIDDEN_EVALUATIVE_FIELD_NAMES,
)
from productiq.retrieval.evaluation.search_evaluation.hardening.integrity import (
    load_json_object,
    validate_baseline_artifact_file,
    validate_evaluation_report_artifact_file,
    verify_declared_checksum,
)
from productiq.retrieval.evaluation.search_evaluation.hardening.invariants import (
    validate_benchmark_query_identity,
    validate_canonical_statistical_comparison_pairs,
    validate_cross_artifact_invariants,
    validate_metric_configuration_identity,
)
from productiq.retrieval.evaluation.search_evaluation.hardening.provenance import (
    validate_provenance_consistency,
)
from productiq.retrieval.evaluation.search_evaluation.reporting.report_builder import (
    build_search_evaluation_report,
)
from productiq.retrieval.evaluation.search_evaluation.reporting.report_loader import (
    load_search_evaluation_report_sources,
)
from productiq.retrieval.evaluation.search_evaluation.reporting.report_schema import (
    SEARCH_EVALUATION_REPORT_FILENAME,
)
from productiq.retrieval.evaluation.search_evaluation.reporting.report_validation import (
    validate_report_sources,
    validate_search_evaluation_report,
)


def _repo_root() -> Path:
    return Path(".")


def _require_canonical_artifacts(root: Path) -> None:
    if not (
        root / "resources/evaluation/productiq_search_benchmark_v1_baseline_bm25_run.json"
    ).is_file():
        pytest.skip("Phase 12 canonical artifacts missing")


@pytest.fixture(scope="module")
def canonical_sources():
    root = _repo_root()
    _require_canonical_artifacts(root)
    return load_search_evaluation_report_sources(root)


class TestArtifactIntegrity:
    def test_valid_baseline_artifact(self) -> None:
        root = _repo_root()
        _require_canonical_artifacts(root)
        path = root / "resources/evaluation" / SEARCH_BASELINE_BM25_RUN_FILENAME
        validate_baseline_artifact_file(path)

    def test_missing_artifact(self, tmp_path: Path) -> None:
        with pytest.raises(RetrievalError, match="artifact not found"):
            load_json_object(tmp_path / "missing.json")

    def test_invalid_json(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.json"
        bad.write_text("{not json", encoding="utf-8")
        with pytest.raises(RetrievalError, match="invalid JSON"):
            load_json_object(bad)

    def test_unsupported_schema(self, tmp_path: Path) -> None:
        root = _repo_root()
        _require_canonical_artifacts(root)
        src = root / "resources/evaluation" / SEARCH_BASELINE_BM25_RUN_FILENAME
        payload = json.loads(src.read_text(encoding="utf-8"))
        payload["artifact_schema_version"] = "99.0.0"
        path = tmp_path / "baseline.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises((RetrievalError, ValueError)):
            validate_baseline_artifact_file(path)

    def test_checksum_mismatch(self, tmp_path: Path) -> None:
        root = _repo_root()
        _require_canonical_artifacts(root)
        src = root / "resources/evaluation" / SEARCH_EVALUATION_REPORT_FILENAME
        if not src.is_file():
            pytest.skip("12.10 report artifact missing")
        payload = json.loads(src.read_text(encoding="utf-8"))
        payload["deterministic_checksum_sha256"] = "0" * 64
        with pytest.raises(RetrievalError, match="checksum"):
            verify_declared_checksum(payload, label="report")


class TestBenchmarkInvariants:
    def test_same_benchmark_accepted(self, canonical_sources: object) -> None:
        validate_cross_artifact_invariants(canonical_sources)

    def test_benchmark_name_mismatch_rejected(self, canonical_sources: object) -> None:
        meta = canonical_sources.benchmark.metadata.model_copy(
            update={"benchmark_name": "other_benchmark"}
        )
        benchmark = canonical_sources.benchmark.model_copy(update={"metadata": meta})
        sources = replace(canonical_sources, benchmark=benchmark)
        with pytest.raises(RetrievalError, match="benchmark identity"):
            validate_report_sources(sources)

    def test_benchmark_version_mismatch_rejected(self, canonical_sources: object) -> None:
        meta = canonical_sources.benchmark.metadata.model_copy(
            update={"benchmark_version": "99.0.0"}
        )
        benchmark = canonical_sources.benchmark.model_copy(update={"metadata": meta})
        sources = replace(canonical_sources, benchmark=benchmark)
        with pytest.raises(RetrievalError, match="benchmark identity"):
            validate_report_sources(sources)

    def test_query_set_mismatch_rejected(self, canonical_sources: object) -> None:
        bundle = canonical_sources.baselines[0]
        per_query = bundle.evaluation_result.per_query[:-1]
        result = bundle.evaluation_result.model_copy(update={"per_query": per_query})
        baselines = (replace(bundle, evaluation_result=result),) + canonical_sources.baselines[1:]
        sources = replace(canonical_sources, baselines=baselines)
        with pytest.raises(RetrievalError, match="query_id set"):
            validate_benchmark_query_identity(sources)

    def test_duplicate_query_rejected(self, canonical_sources: object) -> None:
        duplicate = canonical_sources.benchmark.queries[0]
        queries = canonical_sources.benchmark.queries + (duplicate,)
        benchmark = canonical_sources.benchmark.model_copy(update={"queries": queries})
        sources = replace(canonical_sources, benchmark=benchmark)
        with pytest.raises(RetrievalError, match="duplicate query_id"):
            validate_benchmark_query_identity(sources)


class TestMetricInvariants:
    def test_identical_metric_config_accepted(self, canonical_sources: object) -> None:
        envelope = validate_shared_evaluation_envelope(
            [row.evaluation_result for row in canonical_sources.baselines]
        )
        validate_metric_configuration_identity(
            envelope.metric_configuration,
            envelope.metric_configuration,
            label="self",
        )

    def test_k_mismatch_rejected(self, canonical_sources: object) -> None:
        envelope = validate_shared_evaluation_envelope(
            [row.evaluation_result for row in canonical_sources.baselines]
        )
        other = envelope.metric_configuration.model_copy(update={"k_values": (1, 5, 10, 20)})
        with pytest.raises(RetrievalError, match="incompatible"):
            validate_metric_configuration_identity(
                envelope.metric_configuration,
                other,
                label="k_values",
            )

    def test_execution_top_k_mismatch_rejected(self, canonical_sources: object) -> None:
        envelope = validate_shared_evaluation_envelope(
            [row.evaluation_result for row in canonical_sources.baselines]
        )
        other = envelope.metric_configuration.model_copy(update={"execution_top_k": 5})
        with pytest.raises(RetrievalError, match="incompatible"):
            validate_metric_configuration_identity(
                envelope.metric_configuration,
                other,
                label="execution_top_k",
            )

    def test_evaluation_top_k_mismatch_rejected(self, canonical_sources: object) -> None:
        envelope = validate_shared_evaluation_envelope(
            [row.evaluation_result for row in canonical_sources.baselines]
        )
        other = envelope.metric_configuration.model_copy(update={"evaluation_top_k": 5})
        with pytest.raises(RetrievalError, match="incompatible"):
            validate_metric_configuration_identity(
                envelope.metric_configuration,
                other,
                label="evaluation_top_k",
            )

    def test_min_relevance_threshold_mismatch_rejected(self, canonical_sources: object) -> None:
        envelope = validate_shared_evaluation_envelope(
            [row.evaluation_result for row in canonical_sources.baselines]
        )
        other = envelope.metric_configuration.model_copy(update={"min_relevant_grade": 1})
        with pytest.raises(RetrievalError, match="incompatible"):
            validate_metric_configuration_identity(
                envelope.metric_configuration,
                other,
                label="min_relevant_grade",
            )

    def test_ndcg_configuration_mismatch_rejected(self, canonical_sources: object) -> None:
        envelope = validate_shared_evaluation_envelope(
            [row.evaluation_result for row in canonical_sources.baselines]
        )
        other = envelope.metric_configuration.model_copy(update={"compute_ndcg": False})
        with pytest.raises(RetrievalError, match="incompatible"):
            validate_metric_configuration_identity(
                envelope.metric_configuration,
                other,
                label="compute_ndcg",
            )


class TestProvenance:
    def test_matching_catalog_accepted(self, canonical_sources: object) -> None:
        validate_provenance_consistency(canonical_sources)

    def test_catalog_mismatch_rejected(self, canonical_sources: object) -> None:
        bundle = canonical_sources.baselines[0]
        lineage = bundle.evaluation_result.lineage.model_copy(
            update={"catalog_artifact": "other_catalog.json"}
        )
        result = bundle.evaluation_result.model_copy(update={"lineage": lineage})
        baselines = (replace(bundle, evaluation_result=result),) + canonical_sources.baselines[1:]
        sources = replace(canonical_sources, baselines=baselines)
        with pytest.raises(RetrievalError, match="catalog_artifact"):
            validate_provenance_consistency(sources)

    def test_representation_checksum_mismatch_rejected(self, canonical_sources: object) -> None:
        bundle = canonical_sources.baselines[0]
        lineage = bundle.evaluation_result.lineage.model_copy(
            update={"source_representation_checksum": "deadbeef"}
        )
        result = bundle.evaluation_result.model_copy(update={"lineage": lineage})
        baselines = (replace(bundle, evaluation_result=result),) + canonical_sources.baselines[1:]
        sources = replace(canonical_sources, baselines=baselines)
        with pytest.raises(RetrievalError, match="source_representation_checksum"):
            validate_provenance_consistency(sources)

    def test_duplicate_variant_identity_rejected(self, canonical_sources: object) -> None:
        duplicate = canonical_sources.baselines[0]
        baselines = canonical_sources.baselines + (duplicate,)
        sources = replace(canonical_sources, baselines=baselines)
        with pytest.raises(RetrievalError, match="duplicate"):
            validate_search_evaluation_hardening_sources(sources)


class TestDeterminism:
    def test_report_generated_five_times(self) -> None:
        root = _repo_root()
        _require_canonical_artifacts(root)
        result = validate_report_generation_determinism(root, repetitions=5)
        assert result.repetitions == 5
        assert result.json_stable
        assert result.markdown_stable
        assert len(result.checksum) == 64


class TestFailureModes:
    def test_missing_ltr_artifact_explicit(self) -> None:
        root = _repo_root()
        _present, message = ltr_artifact_status(root)
        assert "LTR artifact" in message

    def test_no_hidden_ltr_fallback_on_canonical_repo(self) -> None:
        from productiq.retrieval.evaluation.search_evaluation.hardening.failure_modes import (
            assert_no_hidden_ltr_fallback,
        )

        assert_no_hidden_ltr_fallback(_repo_root())

    def test_malformed_failure_analysis_rejected(self, tmp_path: Path) -> None:
        from productiq.retrieval.evaluation.search_evaluation.hardening.integrity import (
            validate_failure_analysis_artifact_file,
        )

        path = tmp_path / "failure.json"
        path.write_text(json.dumps({"artifact_schema_version": "12.8.0"}), encoding="utf-8")
        with pytest.raises(RetrievalError):
            validate_failure_analysis_artifact_file(path)

    def test_malformed_statistical_rejected(self, tmp_path: Path) -> None:
        from productiq.retrieval.evaluation.search_evaluation.hardening.integrity import (
            validate_statistical_analysis_artifact_file,
        )

        path = tmp_path / "statistical.json"
        path.write_text(json.dumps({"artifact_schema_version": "12.9.0"}), encoding="utf-8")
        with pytest.raises(RetrievalError):
            validate_statistical_analysis_artifact_file(path)


class TestSafety:
    def test_no_forbidden_evaluative_field_names_in_contract(self) -> None:
        assert "winner" in FORBIDDEN_EVALUATIVE_FIELD_NAMES
        assert "best" in FORBIDDEN_EVALUATIVE_FIELD_NAMES

    def test_report_has_no_winner_fields(self, canonical_sources: object) -> None:
        report = build_search_evaluation_report(canonical_sources)
        validate_search_evaluation_report(report)

    def test_no_metric_recomputation(self, canonical_sources: object) -> None:
        report = build_search_evaluation_report(canonical_sources)
        for bundle in canonical_sources.baselines:
            name = bundle.evaluation_result.lineage.variant_name
            expected_mrr = bundle.evaluation_result.aggregate.mrr
            variant = next(row for row in report.variant_summaries if row.variant_name == name)
            mrr_row = next(row for row in variant.metrics if row.metric_name == "mrr")
            assert mrr_row.value == expected_mrr

    def test_no_statistical_recomputation(self, canonical_sources: object) -> None:
        if canonical_sources.statistical_analysis is None:
            pytest.skip("12.9 artifact missing")
        report = build_search_evaluation_report(canonical_sources)
        source = canonical_sources.statistical_analysis
        for src_row in source.comparisons:
            if src_row.metric_name != "mrr":
                continue
            report_row = next(
                row
                for row in report.statistical_analysis.comparisons
                if row.reference_variant_name == src_row.reference_variant_name
                and row.candidate_variant_name == src_row.candidate_variant_name
                and row.metric_name == "mrr"
            )
            assert report_row.observed_delta == src_row.observed_delta
            assert report_row.p_value == src_row.p_value


class TestCanonicalArtifactValidation:
    def test_persisted_phase12_artifacts_pass_integrity(self) -> None:
        root = _repo_root()
        _require_canonical_artifacts(root)
        validate_persisted_artifact_integrity(root)

    def test_full_hardening_audit_passes(self) -> None:
        root = _repo_root()
        _require_canonical_artifacts(root)
        audit = run_search_evaluation_hardening_audit(
            root,
            include_determinism=True,
            determinism_repetitions=5,
        )
        assert audit.passed
        assert "persisted_artifact_integrity" in audit.checks_passed
        assert audit.determinism is not None

    def test_canonical_statistical_pairs(self, canonical_sources: object) -> None:
        validate_canonical_statistical_comparison_pairs(canonical_sources)

    def test_canonical_report_passes_artifact_validation(self) -> None:
        root = _repo_root()
        path = root / "resources/evaluation" / SEARCH_EVALUATION_REPORT_FILENAME
        if not path.is_file():
            pytest.skip("12.10 report missing")
        validate_evaluation_report_artifact_file(path)
