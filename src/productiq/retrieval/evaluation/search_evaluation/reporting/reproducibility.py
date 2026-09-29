"""Reproducibility manifest for search evaluation reports (Phase 12.10)."""

from __future__ import annotations

from pathlib import Path

from productiq.retrieval.evaluation.search_evaluation.baseline_schema import (
    SEARCH_BASELINE_ARTIFACT_SCHEMA_VERSION,
)
from productiq.retrieval.evaluation.search_evaluation.benchmark_artifact_schema import (
    SEARCH_BENCHMARK_ARTIFACT_SCHEMA_VERSION,
)
from productiq.retrieval.evaluation.search_evaluation.experiment_schema import (
    SEARCH_EXPERIMENT_ARTIFACT_SCHEMA_VERSION,
)
from productiq.retrieval.evaluation.search_evaluation.experiment_validation import (
    validate_shared_evaluation_envelope,
)
from productiq.retrieval.evaluation.search_evaluation.failure_analysis_schema import (
    SEARCH_FAILURE_ANALYSIS_ARTIFACT_SCHEMA_VERSION,
)
from productiq.retrieval.evaluation.search_evaluation.ranking_experiment_schema import (
    SEARCH_RANKING_EXPERIMENT_ARTIFACT_SCHEMA_VERSION,
    SEARCH_RANKING_VARIANT_LTR,
)
from productiq.retrieval.evaluation.search_evaluation.reporting.report_loader import (
    SearchEvaluationReportSources,
)
from productiq.retrieval.evaluation.search_evaluation.reporting.report_schema import (
    SEARCH_EVALUATION_REPORT_ARTIFACT_SCHEMA_VERSION,
    SearchEvaluationReproducibilityManifest,
    SearchEvaluationSourceArtifactReference,
)
from productiq.retrieval.evaluation.search_evaluation.schema import (
    SEARCH_EVALUATION_CONTRACT_VERSION,
)
from productiq.retrieval.evaluation.search_evaluation.statistical_schema import (
    SEARCH_STATISTICAL_ANALYSIS_ARTIFACT_SCHEMA_VERSION,
)

LTR_REFERENCE_ARTIFACT_PATH = "resources/models/ranking_ltr_reference_v10_7_0"
BM25_SCOPED_INDEX_MODE = "benchmark_scoped_slice_4912_docs"


def _checksum(payload: dict[str, object]) -> str | None:
    value = payload.get("deterministic_checksum_sha256")
    return str(value) if isinstance(value, str) else None


def _execution_top_k(bundle_payload: dict[str, object]) -> int:
    config = bundle_payload.get("execution_configuration")
    if isinstance(config, dict):
        raw = config.get("execution_top_k")
        if isinstance(raw, int):
            return raw
    return 50


def build_reproducibility_manifest(
    sources: SearchEvaluationReportSources,
) -> SearchEvaluationReproducibilityManifest:
    baseline_results = [row.evaluation_result for row in sources.baselines]
    envelope = validate_shared_evaluation_envelope(baseline_results)
    execution_top_k = _execution_top_k(sources.baselines[0].payload)

    source_refs: list[SearchEvaluationSourceArtifactReference] = [
        SearchEvaluationSourceArtifactReference(
            pipeline_stage="12.2",
            artifact_path=sources.benchmark_path,
            artifact_schema_version=str(
                sources.benchmark_payload.get(
                    "artifact_schema_version", SEARCH_BENCHMARK_ARTIFACT_SCHEMA_VERSION
                )
            ),
            deterministic_checksum_sha256=_checksum(sources.benchmark_payload),
        ),
    ]
    for bundle in sources.baselines:
        source_refs.append(
            SearchEvaluationSourceArtifactReference(
                pipeline_stage="12.5",
                artifact_path=bundle.artifact_path,
                artifact_schema_version=SEARCH_BASELINE_ARTIFACT_SCHEMA_VERSION,
                deterministic_checksum_sha256=_checksum(bundle.payload),
            )
        )
    if sources.baseline_experiment_payload is not None:
        source_refs.append(
            SearchEvaluationSourceArtifactReference(
                pipeline_stage="12.6",
                artifact_path="resources/evaluation/productiq_search_benchmark_v1_baseline_comparison_experiment_v1.json",
                artifact_schema_version=SEARCH_EXPERIMENT_ARTIFACT_SCHEMA_VERSION,
                deterministic_checksum_sha256=_checksum(sources.baseline_experiment_payload),
            )
        )
    if sources.ranking_experiment_payload is not None:
        source_refs.append(
            SearchEvaluationSourceArtifactReference(
                pipeline_stage="12.7",
                artifact_path="resources/evaluation/productiq_search_ranking_experiment_v1.json",
                artifact_schema_version=SEARCH_RANKING_EXPERIMENT_ARTIFACT_SCHEMA_VERSION,
                deterministic_checksum_sha256=_checksum(sources.ranking_experiment_payload),
            )
        )
    if sources.failure_analysis_payload is not None:
        source_refs.append(
            SearchEvaluationSourceArtifactReference(
                pipeline_stage="12.8",
                artifact_path="resources/evaluation/productiq_search_failure_analysis_v1.json",
                artifact_schema_version=SEARCH_FAILURE_ANALYSIS_ARTIFACT_SCHEMA_VERSION,
                deterministic_checksum_sha256=_checksum(sources.failure_analysis_payload),
            )
        )
    if sources.statistical_analysis_payload is not None:
        source_refs.append(
            SearchEvaluationSourceArtifactReference(
                pipeline_stage="12.9",
                artifact_path="resources/evaluation/productiq_search_statistical_analysis_v1.json",
                artifact_schema_version=SEARCH_STATISTICAL_ANALYSIS_ARTIFACT_SCHEMA_VERSION,
                deterministic_checksum_sha256=_checksum(sources.statistical_analysis_payload),
            )
        )

    variant_identities: list[tuple[str, str]] = []
    variant_checksums: list[tuple[str, str | None]] = []
    index_modes: list[tuple[str, str | None]] = []
    for bundle in sorted(
        sources.baselines, key=lambda row: row.evaluation_result.lineage.variant_name
    ):
        lineage = bundle.evaluation_result.lineage
        variant_identities.append((lineage.variant_name, lineage.variant_version))
        variant_checksums.append((lineage.variant_name, _checksum(bundle.payload)))
        provenance = bundle.payload.get("retrieval_provenance")
        mode: str | None = None
        if isinstance(provenance, dict):
            raw = provenance.get("index_mode") or provenance.get("bm25_index_mode")
            if isinstance(raw, str):
                mode = raw
        index_modes.append((lineage.variant_name, mode))

    if sources.ranking_experiment is not None:
        for result in sources.ranking_experiment.variant_evaluation_results:
            lineage = result.lineage
            variant_identities.append((lineage.variant_name, lineage.variant_version))

    ltr_path = sources.repo_root / Path(LTR_REFERENCE_ARTIFACT_PATH)
    ltr_present = ltr_path.is_dir()

    bootstrap_seed = None
    permutation_seed = None
    multiple_testing = None
    if sources.statistical_analysis is not None:
        bootstrap_seed = sources.statistical_analysis.configuration.bootstrap.random_seed
        permutation_seed = sources.statistical_analysis.configuration.permutation.random_seed
        multiple_testing = sources.statistical_analysis.configuration.multiple_testing_method

    limitations: list[str] = [
        "BM25 baseline runs may use benchmark-scoped retrieval slices rather than full-catalog BM25.",
        "RRF baseline may inherit scoped BM25 retrieval provenance.",
        (
            "LTR ranking results depend on a local Phase 10.7 reference artifact at "
            f"{LTR_REFERENCE_ARTIFACT_PATH}; fresh clones may need retraining or explicit artifact supply."
        ),
        "Statistical summaries reflect the curated 10-query benchmark sample only.",
    ]
    for _name, mode in index_modes:
        if mode == BM25_SCOPED_INDEX_MODE:
            limitations.append(
                f"Variant uses retrieval_index_mode={BM25_SCOPED_INDEX_MODE!r}; not a full-catalog BM25 baseline."
            )
    if sources.ranking_experiment is not None and not ltr_present:
        limitations.append(
            f"LTR artifact directory {LTR_REFERENCE_ARTIFACT_PATH!r} is absent locally; "
            f"12.7 {SEARCH_RANKING_VARIANT_LTR!r} reproducibility may require retraining."
        )

    return SearchEvaluationReproducibilityManifest(
        benchmark_name=envelope.benchmark_name,
        benchmark_version=envelope.benchmark_version,
        evaluation_contract_version=SEARCH_EVALUATION_CONTRACT_VERSION,
        metric_configuration=envelope.metric_configuration,
        execution_top_k=execution_top_k,
        evaluation_top_k=envelope.metric_configuration.evaluation_top_k,
        catalog_artifact=envelope.catalog_artifact,
        source_representation_checksum=envelope.source_representation_checksum,
        source_artifacts=tuple(
            sorted(source_refs, key=lambda row: (row.pipeline_stage, row.artifact_path))
        ),
        variant_identities=tuple(sorted(set(variant_identities))),
        variant_artifact_checksums=tuple(sorted(variant_checksums)),
        retrieval_index_modes=tuple(sorted(index_modes)),
        ltr_artifact_path=LTR_REFERENCE_ARTIFACT_PATH,
        ltr_artifact_present=ltr_present,
        statistical_bootstrap_seed=bootstrap_seed,
        statistical_permutation_seed=permutation_seed,
        statistical_multiple_testing_method=multiple_testing,
        schema_versions=(
            ("12.1", SEARCH_EVALUATION_CONTRACT_VERSION),
            ("12.2", SEARCH_BENCHMARK_ARTIFACT_SCHEMA_VERSION),
            ("12.5", SEARCH_BASELINE_ARTIFACT_SCHEMA_VERSION),
            ("12.6", SEARCH_EXPERIMENT_ARTIFACT_SCHEMA_VERSION),
            ("12.7", SEARCH_RANKING_EXPERIMENT_ARTIFACT_SCHEMA_VERSION),
            ("12.8", SEARCH_FAILURE_ANALYSIS_ARTIFACT_SCHEMA_VERSION),
            ("12.9", SEARCH_STATISTICAL_ANALYSIS_ARTIFACT_SCHEMA_VERSION),
            ("12.10", SEARCH_EVALUATION_REPORT_ARTIFACT_SCHEMA_VERSION),
        ),
        reproducibility_limitations=tuple(dict.fromkeys(limitations)),
    )


__all__ = [
    "BM25_SCOPED_INDEX_MODE",
    "LTR_REFERENCE_ARTIFACT_PATH",
    "build_reproducibility_manifest",
]
