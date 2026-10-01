"""Benchmark artifact integrity checks (Phase 13.8.9)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field
from pydantic import ValidationError as PydanticValidationError

from productiq.serving.performance.concurrency_schema import ConcurrencyBenchmarkSweepResult
from productiq.serving.performance.contract_version import SERVING_PERFORMANCE_CONTRACT_VERSION
from productiq.serving.performance.schema import ServingBenchmarkRunResult

PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_BENCHMARK_ROOT = PROJECT_ROOT / "resources" / "benchmark"
PRODUCT_CATALOG_MANIFEST = PROJECT_ROOT / "resources" / "processed" / "product_catalog.manifest.json"


class ArtifactIntegrityIssue(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    path: str
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)


class ArtifactIntegrityReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    run_results_validated: int = Field(ge=0)
    run_results_failed: int = Field(ge=0)
    sweeps_validated: int = Field(ge=0)
    sweeps_failed: int = Field(ge=0)
    checksum_verifications: int = Field(ge=0)
    checksum_mismatches: int = Field(ge=0)
    issues: tuple[ArtifactIntegrityIssue, ...] = ()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _manifest_catalog_checksum() -> str | None:
    if not PRODUCT_CATALOG_MANIFEST.is_file():
        return None
    payload = json.loads(PRODUCT_CATALOG_MANIFEST.read_text(encoding="utf-8"))
    checksum = payload.get("checksum_sha256") or payload.get("checksum")
    return str(checksum) if checksum else None


def _validate_run_result(path: Path) -> list[ArtifactIntegrityIssue]:
    issues: list[ArtifactIntegrityIssue] = []
    rel = str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")
    try:
        run = ServingBenchmarkRunResult.model_validate_json(path.read_text(encoding="utf-8"))
    except (PydanticValidationError, OSError, json.JSONDecodeError) as exc:
        issues.append(
            ArtifactIntegrityIssue(path=rel, code="invalid_run_json", message=str(exc)),
        )
        return issues

    if run.contract_version != SERVING_PERFORMANCE_CONTRACT_VERSION:
        issues.append(
            ArtifactIntegrityIssue(
                path=rel,
                code="contract_version_mismatch",
                message=f"expected {SERVING_PERFORMANCE_CONTRACT_VERSION}, got {run.contract_version}",
            ),
        )

    err = run.errors
    if err.success_count + err.error_count != err.total_attempts:
        issues.append(
            ArtifactIntegrityIssue(
                path=rel,
                code="error_accounting",
                message="success_count + error_count != total_attempts",
            ),
        )

    if run.latency is not None and run.latency.sample_count != err.success_count:
        issues.append(
            ArtifactIntegrityIssue(
                path=rel,
                code="latency_sample_count",
                message="latency.sample_count must equal errors.success_count",
            ),
        )

    if run.throughput is None:
        issues.append(
            ArtifactIntegrityIssue(path=rel, code="missing_throughput", message="throughput absent"),
        )

    return issues


def _verify_catalog_checksum_in_run(path: Path, run: ServingBenchmarkRunResult) -> ArtifactIntegrityIssue | None:
    recorded = run.serving_configuration.artifact_identifiers.get("product_catalog_checksum_sha256")
    if not recorded:
        return None
    manifest_checksum = _manifest_catalog_checksum()
    if manifest_checksum is None:
        return None
    rel = str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")
    if recorded != manifest_checksum:
        return ArtifactIntegrityIssue(
            path=rel,
            code="checksum_mismatch",
            message="artifact product_catalog_checksum_sha256 does not match manifest",
        )
    catalog_rel = run.serving_configuration.artifact_identifiers.get("catalog_artifact")
    if catalog_rel:
        catalog_path = PROJECT_ROOT / Path(catalog_rel.replace("\\", "/"))
        if catalog_path.is_file():
            file_digest = _sha256_file(catalog_path)
            if file_digest != recorded:
                return ArtifactIntegrityIssue(
                    path=rel,
                    code="checksum_file_mismatch",
                    message="recorded checksum does not match catalog file on disk",
                )
    return None


def _validate_sweep(path: Path) -> list[ArtifactIntegrityIssue]:
    issues: list[ArtifactIntegrityIssue] = []
    rel = str(path.relative_to(PROJECT_ROOT)).replace("\\", "/")
    try:
        sweep = ConcurrencyBenchmarkSweepResult.model_validate_json(path.read_text(encoding="utf-8"))
    except (PydanticValidationError, OSError, json.JSONDecodeError) as exc:
        issues.append(
            ArtifactIntegrityIssue(path=rel, code="invalid_sweep_json", message=str(exc)),
        )
        return issues

    if sweep.sweep_configuration.performance_contract_version != SERVING_PERFORMANCE_CONTRACT_VERSION:
        issues.append(
            ArtifactIntegrityIssue(
                path=rel,
                code="sweep_contract_version",
                message="performance_contract_version mismatch",
            ),
        )

    for run in sweep.run_results:
        if run.errors.success_count + run.errors.error_count != run.errors.total_attempts:
            issues.append(
                ArtifactIntegrityIssue(
                    path=rel,
                    code="sweep_error_accounting",
                    message=f"run {run.provenance.benchmark_run_id} accounting mismatch",
                ),
            )
    return issues


def audit_benchmark_artifact_integrity(
    *,
    benchmark_root: Path | None = None,
    validate_checksums: bool = True,
) -> ArtifactIntegrityReport:
    root = benchmark_root or DEFAULT_BENCHMARK_ROOT
    issues: list[ArtifactIntegrityIssue] = []
    runs_ok = 0
    runs_fail = 0
    sweeps_ok = 0
    sweeps_fail = 0
    checksum_checks = 0
    checksum_bad = 0

    for directory in (
        root / "product_serving",
        root / "search_serving",
        root / "recommendation_serving",
    ):
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.json")):
            if path.name.endswith("_summary.json"):
                continue
            text = path.read_text(encoding="utf-8")
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                issues.append(
                    ArtifactIntegrityIssue(
                        path=str(path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
                        code="invalid_json",
                        message="JSON parse failed",
                    ),
                )
                runs_fail += 1
                continue
            if "configuration" not in payload or "workload" not in payload:
                continue
            run_issues = _validate_run_result(path)
            if validate_checksums and not run_issues:
                run = ServingBenchmarkRunResult.model_validate(payload)
                if run.serving_configuration.artifact_identifiers.get(
                    "product_catalog_checksum_sha256",
                ):
                    checksum_checks += 1
                checksum_issue = _verify_catalog_checksum_in_run(path, run)
                if checksum_issue is not None:
                    checksum_bad += 1
                    run_issues.append(checksum_issue)
            if run_issues:
                runs_fail += 1
                issues.extend(run_issues)
            else:
                runs_ok += 1

    concurrency_dir = root / "concurrency"
    if concurrency_dir.is_dir():
        for path in sorted(concurrency_dir.glob("*_sweep.json")):
            sweep_issues = _validate_sweep(path)
            if sweep_issues:
                sweeps_fail += 1
                issues.extend(sweep_issues)
            else:
                sweeps_ok += 1

    return ArtifactIntegrityReport(
        run_results_validated=runs_ok,
        run_results_failed=runs_fail,
        sweeps_validated=sweeps_ok,
        sweeps_failed=sweeps_fail,
        checksum_verifications=checksum_checks,
        checksum_mismatches=checksum_bad,
        issues=tuple(issues),
    )


__all__ = [
    "ArtifactIntegrityIssue",
    "ArtifactIntegrityReport",
    "audit_benchmark_artifact_integrity",
]
