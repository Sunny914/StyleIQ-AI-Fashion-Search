"""Runtime artifact validation and metadata (Phase 14B)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from productiq.config.runtime_artifacts import (
    RuntimeArtifactPaths,
    RuntimeArtifactSpec,
    resolve_runtime_artifact_paths,
    runtime_artifact_specs,
)
from productiq.config.settings import Settings
from productiq.exceptions.base import ConfigurationError


@dataclass(frozen=True, slots=True)
class ArtifactIntegrityMetadata:
    """Optional checksum/schema metadata read from sidecar manifests."""

    role: str
    manifest_path: Path | None
    checksum_sha256: str | None
    checksum_algorithm: str | None
    schema_version: str | None
    note: str | None = None


@dataclass(frozen=True, slots=True)
class ArtifactValidationResult:
    """Outcome of a single artifact existence check."""

    role: str
    label: str
    ok: bool
    message: str


def _safe_relative(path: Path) -> str:
    try:
        return str(path.as_posix())
    except OSError:
        return "<unavailable>"


def load_optional_manifest_metadata(manifest_path: Path | None) -> ArtifactIntegrityMetadata | None:
    """Read checksum/schema fields when a manifest exists (no parquet/pickle loading)."""
    if manifest_path is None or not manifest_path.is_file():
        return None
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ArtifactIntegrityMetadata(
            role="unknown",
            manifest_path=manifest_path,
            checksum_sha256=None,
            checksum_algorithm=None,
            schema_version=None,
            note="manifest present but could not be parsed",
        )
    checksum = payload.get("checksum")
    return ArtifactIntegrityMetadata(
        role=str(payload.get("dataset_name") or payload.get("index_name") or "artifact"),
        manifest_path=manifest_path,
        checksum_sha256=str(checksum) if checksum else None,
        checksum_algorithm=str(payload.get("checksum_algorithm") or "") or None,
        schema_version=str(payload.get("schema_version") or "") or None,
        note=None if checksum else "checksum not specified in manifest",
    )


def validate_artifact_spec(spec: RuntimeArtifactSpec) -> ArtifactValidationResult:
    """Validate configured path exists (file or directory as specified)."""
    path = spec.resolved_path
    if spec.expects_directory:
        ok = path.is_dir()
        message = "available" if ok else f"Required runtime artifact missing: {spec.label}"
        return ArtifactValidationResult(role=spec.role.value, label=spec.label, ok=ok, message=message)
    ok = path.is_file()
    message = "available" if ok else f"Required runtime artifact missing: {spec.label}"
    return ArtifactValidationResult(role=spec.role.value, label=spec.label, ok=ok, message=message)


def validate_runtime_artifacts(
    settings: Settings,
    *,
    require_roles: frozenset[str] | None = None,
    require_for_full_search_stack: bool = False,
) -> list[ArtifactValidationResult]:
    """Validate artifact existence for deployment checks (no content loading)."""
    paths = resolve_runtime_artifact_paths(settings)
    specs = runtime_artifact_specs(
        paths,
        require_for_full_search_stack=require_for_full_search_stack,
    )
    results: list[ArtifactValidationResult] = []
    for spec in specs:
        if require_roles is not None and spec.role.value not in require_roles:
            continue
        optional_roles = {"bm25_index", "embeddings", "model_artifacts"}
        if (
            require_roles is None
            and not spec.required_for_api
            and not require_for_full_search_stack
            and spec.role.value in optional_roles
        ):
            continue
        results.append(validate_artifact_spec(spec))
    return results


def require_runtime_artifacts(
    settings: Settings,
    *,
    require_roles: frozenset[str],
) -> None:
    """Raise ``ConfigurationError`` when required artifacts are missing."""
    results = validate_runtime_artifacts(settings, require_roles=require_roles)
    failures = [result for result in results if not result.ok]
    if not failures:
        return
    labels = ", ".join(result.label for result in failures)
    msg = f"Runtime deployment artifacts are not available ({labels})"
    raise ConfigurationError(msg)


def collect_artifact_integrity_metadata(
    paths: RuntimeArtifactPaths,
) -> tuple[ArtifactIntegrityMetadata, ...]:
    """Load manifest metadata for known artifacts (best-effort)."""
    specs = runtime_artifact_specs(paths)
    metadata: list[ArtifactIntegrityMetadata] = []
    for spec in specs:
        entry = load_optional_manifest_metadata(spec.manifest_path)
        if entry is not None:
            metadata.append(
                ArtifactIntegrityMetadata(
                    role=spec.role.value,
                    manifest_path=entry.manifest_path,
                    checksum_sha256=entry.checksum_sha256,
                    checksum_algorithm=entry.checksum_algorithm,
                    schema_version=entry.schema_version,
                    note=entry.note,
                ),
            )
        elif spec.manifest_path is not None:
            metadata.append(
                ArtifactIntegrityMetadata(
                    role=spec.role.value,
                    manifest_path=spec.manifest_path,
                    checksum_sha256=None,
                    checksum_algorithm=None,
                    schema_version=None,
                    note="manifest file not present",
                ),
            )
    return tuple(metadata)


def public_artifact_paths(paths: RuntimeArtifactPaths) -> dict[str, str]:
    """Non-secret path summary for diagnostics."""
    return {
        "processed_catalog": _safe_relative(paths.processed_catalog),
        "bm25_index": _safe_relative(paths.bm25_index),
        "embeddings": _safe_relative(paths.embeddings),
        "model_artifacts_dir": _safe_relative(paths.model_artifacts_dir),
    }


__all__ = [
    "ArtifactIntegrityMetadata",
    "ArtifactValidationResult",
    "collect_artifact_integrity_metadata",
    "load_optional_manifest_metadata",
    "public_artifact_paths",
    "require_runtime_artifacts",
    "validate_artifact_spec",
    "validate_runtime_artifacts",
]
