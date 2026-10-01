"""Runtime artifact path resolution (Phase 14B)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from productiq.config.settings import Settings
from productiq.retrieval.embedding_schema import (
    PRODUCT_EMBEDDINGS_FILENAME,
    PRODUCT_EMBEDDINGS_MANIFEST_FILENAME,
)
from productiq.retrieval.index_schema import (
    BM25_LEXICAL_INDEX_FILENAME,
    BM25_LEXICAL_INDEX_MANIFEST_FILENAME,
)

PRODUCT_CATALOG_MANIFEST_FILENAME = "product_catalog.manifest.json"


class ArtifactValidationPhase(StrEnum):
    """When an artifact check is expected to run."""

    DEPLOYMENT_CHECK = "deployment_check"
    FIRST_USE = "first_use"
    STARTUP_OPTIONAL = "startup_optional"


class RuntimeArtifactRole(StrEnum):
    """Known ProductIQ runtime artifact roles."""

    PROCESSED_CATALOG = "processed_catalog"
    BM25_INDEX = "bm25_index"
    EMBEDDINGS = "embeddings"
    MODEL_ARTIFACTS = "model_artifacts"


@dataclass(frozen=True, slots=True)
class RuntimeArtifactPaths:
    """Resolved filesystem locations derived from ``Settings`` (no I/O)."""

    processed_catalog: Path
    processed_catalog_manifest: Path
    bm25_index: Path
    bm25_index_manifest: Path
    embeddings: Path
    embeddings_manifest: Path
    model_artifacts_dir: Path


@dataclass(frozen=True, slots=True)
class RuntimeArtifactSpec:
    """Contract metadata for one runtime artifact."""

    role: RuntimeArtifactRole
    label: str
    resolved_path: Path
    manifest_path: Path | None
    expects_directory: bool
    validation_phase: ArtifactValidationPhase
    required_for_api: bool


def _manifest_beside(data_path: Path, manifest_filename: str) -> Path:
    return data_path.parent / manifest_filename


def resolve_bm25_index_path(settings: Settings) -> Path:
    """Resolve BM25 pickle path from 14A settings and ProductIQ layout conventions."""
    configured = settings.bm25_artifact_path
    if configured.suffix == ".pkl":
        return configured
    nested = configured / BM25_LEXICAL_INDEX_FILENAME
    if nested.is_file():
        return nested
    catalog_parent = settings.processed_catalog_path.parent
    legacy = catalog_parent / BM25_LEXICAL_INDEX_FILENAME
    if legacy.is_file():
        return legacy
    if configured.name == BM25_LEXICAL_INDEX_FILENAME:
        return configured
    return nested if configured.is_dir() else legacy


def resolve_runtime_artifact_paths(settings: Settings) -> RuntimeArtifactPaths:
    """Resolve artifact paths from Settings without loading artifact contents."""
    catalog = settings.processed_catalog_path
    bm25_index = resolve_bm25_index_path(settings)
    embeddings = settings.embeddings_artifact_path
    if embeddings.is_dir():
        embeddings = embeddings / PRODUCT_EMBEDDINGS_FILENAME
    return RuntimeArtifactPaths(
        processed_catalog=catalog,
        processed_catalog_manifest=_manifest_beside(catalog, PRODUCT_CATALOG_MANIFEST_FILENAME),
        bm25_index=bm25_index,
        bm25_index_manifest=_manifest_beside(bm25_index, BM25_LEXICAL_INDEX_MANIFEST_FILENAME),
        embeddings=embeddings,
        embeddings_manifest=_manifest_beside(embeddings, PRODUCT_EMBEDDINGS_MANIFEST_FILENAME),
        model_artifacts_dir=settings.model_artifacts_dir,
    )


def runtime_artifact_specs(
    paths: RuntimeArtifactPaths,
    *,
    require_for_full_search_stack: bool = False,
) -> tuple[RuntimeArtifactSpec, ...]:
    """Describe runtime artifacts for validation and deployment documentation."""
    search_stack_required = require_for_full_search_stack
    return (
        RuntimeArtifactSpec(
            role=RuntimeArtifactRole.PROCESSED_CATALOG,
            label="Processed product catalog",
            resolved_path=paths.processed_catalog,
            manifest_path=paths.processed_catalog_manifest,
            expects_directory=False,
            validation_phase=ArtifactValidationPhase.FIRST_USE,
            required_for_api=True,
        ),
        RuntimeArtifactSpec(
            role=RuntimeArtifactRole.BM25_INDEX,
            label="BM25 lexical index",
            resolved_path=paths.bm25_index,
            manifest_path=paths.bm25_index_manifest,
            expects_directory=False,
            validation_phase=ArtifactValidationPhase.FIRST_USE,
            required_for_api=search_stack_required,
        ),
        RuntimeArtifactSpec(
            role=RuntimeArtifactRole.EMBEDDINGS,
            label="Product embedding artifact",
            resolved_path=paths.embeddings,
            manifest_path=paths.embeddings_manifest,
            expects_directory=False,
            validation_phase=ArtifactValidationPhase.DEPLOYMENT_CHECK,
            required_for_api=search_stack_required,
        ),
        RuntimeArtifactSpec(
            role=RuntimeArtifactRole.MODEL_ARTIFACTS,
            label="Model artifact directory",
            resolved_path=paths.model_artifacts_dir,
            manifest_path=None,
            expects_directory=True,
            validation_phase=ArtifactValidationPhase.DEPLOYMENT_CHECK,
            required_for_api=False,
        ),
    )


__all__ = [
    "PRODUCT_CATALOG_MANIFEST_FILENAME",
    "ArtifactValidationPhase",
    "RuntimeArtifactPaths",
    "RuntimeArtifactRole",
    "RuntimeArtifactSpec",
    "resolve_bm25_index_path",
    "resolve_runtime_artifact_paths",
    "runtime_artifact_specs",
]
