"""Execute search evaluation experiments from baseline artifact references (Phase 12.6)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from productiq.exceptions.base import RetrievalError
from productiq.retrieval.evaluation.search_evaluation.baseline_artifact import (
    deterministic_artifact_checksum,
)
from productiq.retrieval.evaluation.search_evaluation.baseline_schema import (
    SEARCH_BASELINE_BM25_RUN_FILENAME,
    SEARCH_BASELINE_BM25_VARIANT_NAME,
    SEARCH_BASELINE_RRF_RUN_FILENAME,
    SEARCH_BASELINE_RRF_VARIANT_NAME,
    SEARCH_BASELINE_SEMANTIC_RUN_FILENAME,
    SEARCH_BASELINE_SEMANTIC_VARIANT_NAME,
)
from productiq.retrieval.evaluation.search_evaluation.comparison import (
    compare_search_evaluation_variants,
)
from productiq.retrieval.evaluation.search_evaluation.experiment_loader import (
    artifact_reference_from_baseline_payload,
    load_variant_evaluation_from_baseline_artifact,
)
from productiq.retrieval.evaluation.search_evaluation.experiment_schema import (
    SEARCH_BASELINE_COMPARISON_EXPERIMENT_FILENAME,
    SEARCH_BASELINE_COMPARISON_EXPERIMENT_NAME,
    SEARCH_BASELINE_COMPARISON_EXPERIMENT_VERSION,
    SEARCH_EXPERIMENT_ARTIFACT_SCHEMA_VERSION,
    SearchBaselineArtifactReference,
    SearchEvaluationExperimentDefinition,
    SearchEvaluationExperimentResult,
    search_evaluation_experiment_result_to_dict,
)
from productiq.retrieval.evaluation.search_evaluation.experiment_validation import (
    validate_shared_evaluation_envelope,
)
from productiq.retrieval.evaluation.search_evaluation.result_schema import (
    SearchVariantEvaluationResult,
)


def _relative_artifact_path(repo_root: Path, path: Path, fallback: str) -> str:
    try:
        return str(path.relative_to(repo_root)).replace("\\", "/")
    except ValueError:
        return fallback


def _resolve_artifact_path(repo_root: Path, artifact_path: str) -> Path:
    path = Path(artifact_path)
    if path.is_file():
        return path
    candidate = repo_root / artifact_path
    if candidate.is_file():
        return candidate
    msg = f"experiment artifact not found: {artifact_path}"
    raise RetrievalError(msg)


def _provenance_notes(
    references: tuple[SearchBaselineArtifactReference, ...],
) -> tuple[str, ...]:
    notes: list[str] = [
        "Experiment comparisons report absolute metric deltas only.",
        "No winner, best variant, or recommendation is selected.",
    ]
    for row in references:
        if row.retrieval_index_mode and "benchmark_scoped" in row.retrieval_index_mode:
            notes.append(
                f"Variant {row.variant_name!r} used BM25 index mode "
                f"{row.retrieval_index_mode!r}; not a full-catalog BM25 run."
            )
    return tuple(notes)


def run_search_evaluation_experiment(
    definition: SearchEvaluationExperimentDefinition,
    repo_root: Path,
    *,
    validate_checksums: bool = True,
) -> SearchEvaluationExperimentResult:
    """Load baseline artifacts, validate envelope, compute descriptive deltas vs reference."""
    root = Path(repo_root)
    loaded_results: dict[str, SearchVariantEvaluationResult] = {}
    resolved_references: list[SearchBaselineArtifactReference] = []

    for slot in sorted(definition.variant_artifacts, key=lambda row: row.variant_name):
        path = _resolve_artifact_path(root, slot.artifact_path)
        result, payload = load_variant_evaluation_from_baseline_artifact(
            path,
            reference=slot if validate_checksums else None,
            validate_checksum=validate_checksums,
        )
        rel_path = _relative_artifact_path(root, path, slot.artifact_path)
        resolved_references.append(
            artifact_reference_from_baseline_payload(artifact_path=rel_path, payload=payload)
        )
        if result.lineage.variant_name != slot.variant_name:
            msg = (
                f"evaluation result variant {result.lineage.variant_name!r} "
                f"does not match experiment slot {slot.variant_name!r}"
            )
            raise RetrievalError(msg)
        loaded_results[slot.variant_name] = result

    ordered_results = tuple(loaded_results[name] for name in sorted(loaded_results.keys()))
    envelope = validate_shared_evaluation_envelope(ordered_results)

    reference_name = definition.reference_variant_name
    if reference_name not in loaded_results:
        msg = f"reference variant {reference_name!r} missing from loaded results"
        raise RetrievalError(msg)
    reference_result = loaded_results[reference_name]

    comparisons = []
    for candidate_name in sorted(loaded_results.keys()):
        if candidate_name == reference_name:
            continue
        candidate_result = loaded_results[candidate_name]
        comparisons.append(compare_search_evaluation_variants(reference_result, candidate_result))

    return SearchEvaluationExperimentResult(
        experiment_name=definition.experiment_name,
        experiment_version=definition.experiment_version,
        description=definition.description,
        reference_variant_name=reference_name,
        envelope=envelope,
        variant_artifact_references=tuple(resolved_references),
        candidate_comparisons=tuple(comparisons),
        provenance_notes=_provenance_notes(tuple(resolved_references)),
    )


def build_default_baseline_comparison_experiment_definition(
    repo_root: Path,
    *,
    reference_variant_name: str = SEARCH_BASELINE_BM25_VARIANT_NAME,
) -> SearchEvaluationExperimentDefinition:
    """Build experiment definition pointing at Phase 12.5 baseline artifacts (checksums from disk)."""
    root = Path(repo_root)
    eval_dir = root / "resources" / "evaluation"
    slots: list[SearchBaselineArtifactReference] = []
    for _variant_name, filename in (
        (SEARCH_BASELINE_BM25_VARIANT_NAME, SEARCH_BASELINE_BM25_RUN_FILENAME),
        (SEARCH_BASELINE_SEMANTIC_VARIANT_NAME, SEARCH_BASELINE_SEMANTIC_RUN_FILENAME),
        (SEARCH_BASELINE_RRF_VARIANT_NAME, SEARCH_BASELINE_RRF_RUN_FILENAME),
    ):
        path = eval_dir / filename
        if not path.is_file():
            msg = f"missing Phase 12.5 baseline artifact: {path}"
            raise RetrievalError(msg)
        _, payload = load_variant_evaluation_from_baseline_artifact(path, validate_checksum=True)
        rel = f"resources/evaluation/{filename}"
        slots.append(artifact_reference_from_baseline_payload(artifact_path=rel, payload=payload))
    if reference_variant_name not in {row.variant_name for row in slots}:
        msg = f"reference variant {reference_variant_name!r} not among baseline artifacts"
        raise RetrievalError(msg)
    return SearchEvaluationExperimentDefinition(
        experiment_name=SEARCH_BASELINE_COMPARISON_EXPERIMENT_NAME,
        experiment_version=SEARCH_BASELINE_COMPARISON_EXPERIMENT_VERSION,
        description=(
            "Descriptive comparison of Phase 12.5 search baselines on "
            "productiq_search_benchmark_v1 using BM25 as numerical reference."
        ),
        reference_variant_name=reference_variant_name,
        variant_artifacts=tuple(sorted(slots, key=lambda row: row.variant_name)),
    )


def build_experiment_artifact_dict(
    definition: SearchEvaluationExperimentDefinition,
    result: SearchEvaluationExperimentResult,
) -> dict[str, Any]:
    body = {
        "artifact_schema_version": SEARCH_EXPERIMENT_ARTIFACT_SCHEMA_VERSION,
        "experiment_definition": definition.model_dump(mode="json"),
        "experiment_result": search_evaluation_experiment_result_to_dict(result),
    }
    body["deterministic_checksum_sha256"] = deterministic_artifact_checksum(body)
    return body


def write_search_experiment_artifact(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def run_default_baseline_comparison_experiment(repo_root: Path) -> SearchEvaluationExperimentResult:
    definition = build_default_baseline_comparison_experiment_definition(repo_root)
    result = run_search_evaluation_experiment(definition, repo_root)
    out_path = (
        Path(repo_root)
        / "resources"
        / "evaluation"
        / SEARCH_BASELINE_COMPARISON_EXPERIMENT_FILENAME
    )
    write_search_experiment_artifact(out_path, build_experiment_artifact_dict(definition, result))
    return result


__all__ = [
    "build_default_baseline_comparison_experiment_definition",
    "build_experiment_artifact_dict",
    "run_default_baseline_comparison_experiment",
    "run_search_evaluation_experiment",
    "write_search_experiment_artifact",
]
