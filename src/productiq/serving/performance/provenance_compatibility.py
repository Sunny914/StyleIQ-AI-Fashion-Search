"""Provenance compatibility rules for baseline comparison (Phase 13.8.7)."""

from __future__ import annotations

from productiq.serving.performance.baseline_identity import identities_match
from productiq.serving.performance.baseline_schema import (
    BenchmarkRunIdentity,
    ProvenanceCompatibilityResult,
    ProvenanceCompatibilityStatus,
    ServingPerformanceBaselineRecord,
)
from productiq.serving.performance.schema import ServingBenchmarkRunResult


def _artifact_identifier_mismatches(
    baseline_ids: dict[str, str],
    current_ids: dict[str, str],
) -> tuple[str, ...]:
    differences: list[str] = []
    shared_keys = sorted(set(baseline_ids) & set(current_ids))
    for key in shared_keys:
        if baseline_ids[key] != current_ids[key]:
            differences.append(f"artifact_identifiers.{key}: values differ")
    return tuple(differences)


def assess_provenance_compatibility(
    baseline: ServingPerformanceBaselineRecord,
    current: ServingBenchmarkRunResult,
    *,
    current_identity: BenchmarkRunIdentity,
) -> ProvenanceCompatibilityResult:
    mismatches: list[str] = []
    identity_ok, identity_mismatches = identities_match(baseline.identity, current_identity)
    mismatches.extend(identity_mismatches)

    if baseline.performance_contract_version != current.contract_version:
        mismatches.append(
            "performance_contract_version: "
            f"{baseline.performance_contract_version} != {current.contract_version}",
        )
    base_prov = baseline.result.provenance
    cur_prov = current.provenance
    if base_prov.runner_version != cur_prov.runner_version:
        mismatches.append(
            f"runner_version: {base_prov.runner_version!r} != {cur_prov.runner_version!r}",
        )

    provenance_differences: list[str] = []
    if baseline.environment.platform != current.environment.platform:
        provenance_differences.append("environment.platform differs (comparison may not be portable)")
    if baseline.environment.python_version != current.environment.python_version:
        provenance_differences.append("environment.python_version differs")

    artifact_diffs = _artifact_identifier_mismatches(
        baseline.serving_configuration.artifact_identifiers,
        current.serving_configuration.artifact_identifiers,
    )
    mismatches.extend(artifact_diffs)

    if mismatches:
        return ProvenanceCompatibilityResult(
            status=ProvenanceCompatibilityStatus.INCOMPATIBLE,
            compatible=False,
            mismatches=tuple(mismatches),
            provenance_differences=tuple(provenance_differences),
        )
    return ProvenanceCompatibilityResult(
        status=ProvenanceCompatibilityStatus.COMPATIBLE,
        compatible=True,
        mismatches=(),
        provenance_differences=tuple(provenance_differences),
    )


__all__ = ["assess_provenance_compatibility"]
