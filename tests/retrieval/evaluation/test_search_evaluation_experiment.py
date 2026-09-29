"""Tests for Phase 12.6 search evaluation experiment framework."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from productiq.exceptions.base import RetrievalError
from productiq.retrieval.evaluation.search_evaluation.baseline_artifact import (
    build_baseline_run_artifact,
    write_baseline_run_artifact,
)
from productiq.retrieval.evaluation.search_evaluation.baseline_schema import (
    SEARCH_BASELINE_BM25_RUN_FILENAME,
    SEARCH_BASELINE_BM25_VARIANT_NAME,
    SEARCH_BASELINE_RRF_RUN_FILENAME,
    SEARCH_BASELINE_RRF_VARIANT_NAME,
    SEARCH_BASELINE_SEMANTIC_RUN_FILENAME,
    SEARCH_BASELINE_SEMANTIC_VARIANT_NAME,
)
from productiq.retrieval.evaluation.search_evaluation.experiment_loader import (
    artifact_reference_from_baseline_payload,
    load_variant_evaluation_from_baseline_artifact,
)
from productiq.retrieval.evaluation.search_evaluation.experiment_runner import (
    build_default_baseline_comparison_experiment_definition,
    build_experiment_artifact_dict,
    run_search_evaluation_experiment,
)
from productiq.retrieval.evaluation.search_evaluation.experiment_schema import (
    SEARCH_BASELINE_COMPARISON_EXPERIMENT_NAME,
    SearchBaselineArtifactReference,
    SearchEvaluationExperimentDefinition,
    SearchEvaluationExperimentResult,
    search_evaluation_experiment_result_to_dict,
)
from productiq.retrieval.evaluation.search_evaluation.experiment_validation import (
    validate_shared_evaluation_envelope,
)
from productiq.retrieval.evaluation.search_evaluation.request_schema import (
    SearchMetricConfiguration,
)
from productiq.retrieval.evaluation.search_evaluation.result_schema import (
    SearchAggregateMetricResult,
    SearchEvaluationLineage,
    SearchQueryMetricResult,
    SearchVariantEvaluationResult,
)


def _metric_config(
    *,
    evaluation_top_k: int = 50,
    execution_top_k: int = 50,
    k_values: tuple[int, ...] = (1, 5, 10),
) -> SearchMetricConfiguration:
    return SearchMetricConfiguration(
        k_values=k_values,
        evaluation_top_k=evaluation_top_k,
        execution_top_k=execution_top_k,
        min_relevant_grade=2,
        compute_ndcg=True,
    )


def _variant_result(
    *,
    variant_name: str,
    mrr: float,
    metric_configuration: SearchMetricConfiguration | None = None,
    benchmark_name: str = "productiq_search_benchmark_v1",
    benchmark_version: str = "1.0.0",
    catalog_artifact: str | None = "resources/evaluation/productiq_search_benchmark_v1.json",
    source_checksum: str | None = "checksum-a",
) -> SearchVariantEvaluationResult:
    config = metric_configuration or _metric_config()
    lineage = SearchEvaluationLineage(
        benchmark_name=benchmark_name,
        benchmark_version=benchmark_version,
        variant_name=variant_name,
        variant_version="1.0.0",
        metric_configuration=config,
        catalog_artifact=catalog_artifact,
        source_representation_checksum=source_checksum,
    )
    k_values = config.k_values
    per_query = (
        SearchQueryMetricResult(
            query_id="q1",
            query_text="alpha",
            query_category="test",
            judged_relevant_count=1,
            ranked_product_ids=("P1",),
            precision_at_k={k: 1.0 for k in k_values},
            recall_at_k={k: (None if k == 1 else 1.0) for k in k_values},
            hit_rate_at_k={k: 1.0 for k in k_values},
            ndcg_at_k={k: (None if k == 5 else 0.8) for k in k_values},
            reciprocal_rank=1.0,
            recall_aggregate_eligible=True,
        ),
    )
    aggregate = SearchAggregateMetricResult(
        query_count=1,
        recall_aggregate_query_count=1,
        ndcg_aggregate_query_count=1,
        k_values=k_values,
        mean_precision_at_k={k: 0.1 * k for k in k_values},
        mean_recall_at_k={k: 0.2 * k for k in k_values},
        mean_hit_rate_at_k={k: 0.3 * k for k in k_values},
        mean_ndcg_at_k={k: 0.4 * k for k in k_values},
        mrr=mrr,
    )
    return SearchVariantEvaluationResult(lineage=lineage, per_query=per_query, aggregate=aggregate)


def _write_baseline_artifact(
    tmp_path: Path,
    result: SearchVariantEvaluationResult,
    *,
    filename: str,
    index_mode: str | None = None,
) -> Path:
    provenance: dict[str, object] = {"retrieval_mode": "toy"}
    if index_mode is not None:
        provenance["index_mode"] = index_mode
    artifact = build_baseline_run_artifact(
        result,
        retrieval_provenance=provenance,
        runtime_metadata={"evaluation_duration_seconds": 0.0},
    )
    path = tmp_path / filename
    write_baseline_run_artifact(path, artifact)
    return path


def _artifact_ref(path: Path, rel: str) -> SearchBaselineArtifactReference:
    _, payload = load_variant_evaluation_from_baseline_artifact(path)
    return artifact_reference_from_baseline_payload(artifact_path=rel, payload=payload)


def _experiment_definition(
    tmp_path: Path,
    *,
    reference: str = "variant_a",
    mrr_by_variant: dict[str, float] | None = None,
) -> SearchEvaluationExperimentDefinition:
    mrr_by_variant = mrr_by_variant or {"variant_a": 0.5, "variant_b": 0.7}
    refs: list[SearchBaselineArtifactReference] = []
    for name, mrr in sorted(mrr_by_variant.items()):
        result = _variant_result(variant_name=name, mrr=mrr)
        path = _write_baseline_artifact(tmp_path, result, filename=f"{name}.json")
        refs.append(_artifact_ref(path, f"{name}.json"))
    return SearchEvaluationExperimentDefinition(
        experiment_name="toy_experiment",
        experiment_version="1.0.0",
        description="unit test experiment",
        reference_variant_name=reference,
        variant_artifacts=tuple(refs),
    )


class TestExperimentDefinition:
    def test_valid_experiment_construction(self, tmp_path: Path) -> None:
        definition = _experiment_definition(tmp_path)
        assert definition.reference_variant_name == "variant_a"
        assert len(definition.variant_artifacts) == 2

    def test_invalid_experiment_identity_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SearchEvaluationExperimentDefinition(
                experiment_name="",
                experiment_version="1.0.0",
                reference_variant_name="a",
                variant_artifacts=(
                    SearchBaselineArtifactReference(
                        variant_name="a",
                        variant_version="1.0.0",
                        artifact_path="a.json",
                    ),
                    SearchBaselineArtifactReference(
                        variant_name="b",
                        variant_version="1.0.0",
                        artifact_path="b.json",
                    ),
                ),
            )

    def test_duplicate_variants_rejected(self) -> None:
        with pytest.raises(ValidationError, match="unique"):
            SearchEvaluationExperimentDefinition(
                experiment_name="dup",
                experiment_version="1.0.0",
                reference_variant_name="a",
                variant_artifacts=(
                    SearchBaselineArtifactReference(
                        variant_name="a",
                        variant_version="1.0.0",
                        artifact_path="a.json",
                    ),
                    SearchBaselineArtifactReference(
                        variant_name="a",
                        variant_version="1.0.0",
                        artifact_path="a2.json",
                    ),
                ),
            )

    def test_missing_variant_version_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SearchBaselineArtifactReference(
                variant_name="a",
                variant_version="",
                artifact_path="a.json",
            )

    def test_reference_variant_must_exist_among_artifacts(self) -> None:
        with pytest.raises(ValidationError, match="reference_variant_name"):
            SearchEvaluationExperimentDefinition(
                experiment_name="missing_ref",
                experiment_version="1.0.0",
                reference_variant_name="ghost",
                variant_artifacts=(
                    SearchBaselineArtifactReference(
                        variant_name="a",
                        variant_version="1.0.0",
                        artifact_path="a.json",
                    ),
                    SearchBaselineArtifactReference(
                        variant_name="b",
                        variant_version="1.0.0",
                        artifact_path="b.json",
                    ),
                ),
            )

    def test_single_reference_field_only(self) -> None:
        fields = SearchEvaluationExperimentDefinition.model_fields
        assert "reference_variant_name" in fields
        forbidden = {"winner", "best_variant", "recommended_variant", "ranking"}
        assert forbidden.isdisjoint(fields.keys())


class TestEnvelopeValidation:
    def test_compatible_envelopes(self) -> None:
        a = _variant_result(variant_name="a", mrr=0.1)
        b = _variant_result(variant_name="b", mrr=0.2)
        envelope = validate_shared_evaluation_envelope((a, b))
        assert envelope.benchmark_name == "productiq_search_benchmark_v1"

    def test_incompatible_benchmark(self) -> None:
        a = _variant_result(variant_name="a", mrr=0.1)
        b = _variant_result(variant_name="b", mrr=0.2, benchmark_version="9.9.9")
        with pytest.raises(RetrievalError, match="benchmark"):
            validate_shared_evaluation_envelope((a, b))

    def test_incompatible_metric_configuration(self) -> None:
        a = _variant_result(variant_name="a", mrr=0.1)
        other_config = _metric_config().model_copy(update={"min_relevant_grade": 3})
        b = _variant_result(variant_name="b", mrr=0.2, metric_configuration=other_config)
        with pytest.raises(RetrievalError, match="metric_configuration"):
            validate_shared_evaluation_envelope((a, b))

    def test_incompatible_evaluation_top_k(self) -> None:
        a = _variant_result(
            variant_name="a", mrr=0.1, metric_configuration=_metric_config(evaluation_top_k=50)
        )
        b = _variant_result(
            variant_name="b",
            mrr=0.2,
            metric_configuration=_metric_config(evaluation_top_k=20),
        )
        with pytest.raises(RetrievalError, match="metric_configuration"):
            validate_shared_evaluation_envelope((a, b))

    def test_incompatible_execution_top_k(self) -> None:
        a = _variant_result(
            variant_name="a", mrr=0.1, metric_configuration=_metric_config(execution_top_k=50)
        )
        b = _variant_result(
            variant_name="b",
            mrr=0.2,
            metric_configuration=_metric_config(execution_top_k=10),
        )
        with pytest.raises(RetrievalError, match="metric_configuration"):
            validate_shared_evaluation_envelope((a, b))


class TestExperimentRunner:
    def test_comparison_delta_calculation(self, tmp_path: Path) -> None:
        definition = _experiment_definition(
            tmp_path,
            mrr_by_variant={"variant_a": 0.5, "variant_b": 0.8},
        )
        result = run_search_evaluation_experiment(definition, tmp_path)
        assert result.reference_variant_name == "variant_a"
        assert len(result.candidate_comparisons) == 1
        comparison = result.candidate_comparisons[0]
        assert comparison.baseline_variant == "variant_a"
        assert comparison.comparison_variant == "variant_b"
        assert comparison.mrr_delta == pytest.approx(0.3)
        for k in (1, 5, 10):
            assert comparison.precision_at_k_delta[k] == pytest.approx(0.0)

    def test_multiple_k_values_in_deltas(self, tmp_path: Path) -> None:
        config = _metric_config(k_values=(1, 5, 10, 20))
        refs: list[SearchBaselineArtifactReference] = []
        for name, mrr in (("ref", 0.4), ("cand", 0.6)):
            path = _write_baseline_artifact(
                tmp_path,
                _variant_result(variant_name=name, mrr=mrr, metric_configuration=config),
                filename=f"{name}.json",
            )
            refs.append(_artifact_ref(path, f"{name}.json"))
        definition = SearchEvaluationExperimentDefinition(
            experiment_name="multi_k",
            experiment_version="1.0.0",
            reference_variant_name="ref",
            variant_artifacts=tuple(refs),
        )
        result = run_search_evaluation_experiment(definition, tmp_path)
        delta = result.candidate_comparisons[0]
        assert set(delta.precision_at_k_delta.keys()) == {1, 5, 10, 20}

    def test_per_query_none_preserved_in_loaded_artifact(self, tmp_path: Path) -> None:
        definition = _experiment_definition(tmp_path)
        result = run_search_evaluation_experiment(definition, tmp_path)
        loaded_name = next(iter(result.variant_artifact_references)).variant_name
        path = tmp_path / f"{loaded_name}.json"
        _, payload = load_variant_evaluation_from_baseline_artifact(path)
        per_query = payload["evaluation_result"]["per_query"][0]
        assert per_query["recall_at_k"]["1"] is None
        assert per_query["ndcg_at_k"]["5"] is None

    def test_deterministic_serialization(self, tmp_path: Path) -> None:
        definition = _experiment_definition(tmp_path)
        result = run_search_evaluation_experiment(definition, tmp_path)
        payload = build_experiment_artifact_dict(definition, result)
        again = json.dumps(payload, sort_keys=True)
        assert again == json.dumps(payload, sort_keys=True)
        serialized = search_evaluation_experiment_result_to_dict(result)
        dumped = json.dumps(serialized, sort_keys=True)
        assert '"winner"' not in dumped
        assert '"best_variant"' not in dumped
        assert '"recommended_variant"' not in dumped

    def test_artifact_checksum_validation(self, tmp_path: Path) -> None:
        definition = _experiment_definition(tmp_path)
        bad_ref = definition.variant_artifacts[0].model_copy(
            update={"deterministic_checksum_sha256": "0" * 64}
        )
        bad_definition = definition.model_copy(
            update={"variant_artifacts": (bad_ref,) + definition.variant_artifacts[1:]}
        )
        with pytest.raises(RetrievalError, match="checksum mismatch"):
            run_search_evaluation_experiment(bad_definition, tmp_path)

    def test_variant_name_mismatch_rejected(self, tmp_path: Path) -> None:
        path = _write_baseline_artifact(
            tmp_path,
            _variant_result(variant_name="actual", mrr=0.5),
            filename="slot.json",
        )
        ref = SearchBaselineArtifactReference(
            variant_name="expected",
            variant_version="1.0.0",
            artifact_path=str(path),
        )
        definition = SearchEvaluationExperimentDefinition(
            experiment_name="mismatch",
            experiment_version="1.0.0",
            reference_variant_name="expected",
            variant_artifacts=(
                ref,
                _artifact_ref(
                    _write_baseline_artifact(
                        tmp_path,
                        _variant_result(variant_name="other", mrr=0.6),
                        filename="other.json",
                    ),
                    "other.json",
                ),
            ),
        )
        with pytest.raises(RetrievalError, match="does not match experiment slot"):
            run_search_evaluation_experiment(definition, tmp_path, validate_checksums=False)

    def test_bm25_scoped_provenance_note(self, tmp_path: Path) -> None:
        refs: list[SearchBaselineArtifactReference] = []
        for name, mode in (
            ("variant_a", "benchmark_scoped_slice_4912_docs"),
            ("variant_b", None),
        ):
            path = _write_baseline_artifact(
                tmp_path,
                _variant_result(variant_name=name, mrr=0.5),
                filename=f"{name}.json",
                index_mode=mode,
            )
            refs.append(_artifact_ref(path, f"{name}.json"))
        definition = SearchEvaluationExperimentDefinition(
            experiment_name="scoped",
            experiment_version="1.0.0",
            reference_variant_name="variant_a",
            variant_artifacts=tuple(refs),
        )
        result = run_search_evaluation_experiment(definition, tmp_path)
        notes = " ".join(result.provenance_notes)
        assert "benchmark_scoped" in notes
        assert "not a full-catalog BM25 run" in notes

    def test_result_has_no_winner_fields(self, tmp_path: Path) -> None:
        result = run_search_evaluation_experiment(_experiment_definition(tmp_path), tmp_path)
        fields = SearchEvaluationExperimentResult.model_fields
        forbidden = {"winner", "best_variant", "recommended_variant", "rank_order"}
        assert forbidden.isdisjoint(fields.keys())
        blob = json.dumps(search_evaluation_experiment_result_to_dict(result))
        assert '"winner"' not in blob


class TestPhase125ArtifactIntegration:
    @pytest.fixture
    def repo_root(self) -> Path:
        return Path(".")

    def test_default_definition_points_at_baselines(self, repo_root: Path) -> None:
        bm25 = repo_root / "resources" / "evaluation" / SEARCH_BASELINE_BM25_RUN_FILENAME
        if not bm25.is_file():
            pytest.skip("Phase 12.5 BM25 baseline artifact not present")
        definition = build_default_baseline_comparison_experiment_definition(repo_root)
        assert definition.experiment_name == SEARCH_BASELINE_COMPARISON_EXPERIMENT_NAME
        names = {row.variant_name for row in definition.variant_artifacts}
        assert names == {
            SEARCH_BASELINE_BM25_VARIANT_NAME,
            SEARCH_BASELINE_SEMANTIC_VARIANT_NAME,
            SEARCH_BASELINE_RRF_VARIANT_NAME,
        }

    def test_run_default_experiment_on_real_artifacts(self, repo_root: Path) -> None:
        eval_dir = repo_root / "resources" / "evaluation"
        required = (
            SEARCH_BASELINE_BM25_RUN_FILENAME,
            SEARCH_BASELINE_SEMANTIC_RUN_FILENAME,
            SEARCH_BASELINE_RRF_RUN_FILENAME,
        )
        if not all((eval_dir / name).is_file() for name in required):
            pytest.skip("Phase 12.5 baseline artifacts not present")
        definition = build_default_baseline_comparison_experiment_definition(repo_root)
        result = run_search_evaluation_experiment(definition, repo_root)
        assert result.reference_variant_name == SEARCH_BASELINE_BM25_VARIANT_NAME
        assert len(result.candidate_comparisons) == 2
        bm25_ref = next(
            row
            for row in result.variant_artifact_references
            if row.variant_name == SEARCH_BASELINE_BM25_VARIANT_NAME
        )
        assert bm25_ref.retrieval_index_mode == "benchmark_scoped_slice_4912_docs"
