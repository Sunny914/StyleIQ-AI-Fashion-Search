"""ProductIQ deployment / runtime manifest (Phase 14B)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from productiq.config.database_runtime import (
    postgres_runtime_contract,
    summarize_database_configuration,
)
from productiq.config.runtime_artifacts import resolve_runtime_artifact_paths
from productiq.config.runtime_validation import (
    collect_artifact_integrity_metadata,
    public_artifact_paths,
)
from productiq.config.settings import Settings
from productiq.serving.config import ServingConfig
from productiq.serving.versioning import SERVING_API_MAJOR_VERSION

MANIFEST_VERSION = "1.0.0"
DEFAULT_MANIFEST_PATH = Path("resources/deployment/productiq_deployment_manifest.json")


def build_deployment_manifest(
    *,
    settings: Settings,
    serving: ServingConfig | None = None,
) -> dict[str, Any]:
    """Build a concise runtime dependency manifest for operators."""
    serving_config = serving or ServingConfig()
    paths = resolve_runtime_artifact_paths(settings)
    db = summarize_database_configuration(settings)
    pg = postgres_runtime_contract()
    integrity = collect_artifact_integrity_metadata(paths)
    return {
        "manifest_version": MANIFEST_VERSION,
        "application": {
            "name": settings.app_name,
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}",
            "api_entrypoint": "productiq.api.app:create_app",
            "api_version": serving_config.api_version,
            "serving_api_major_version": SERVING_API_MAJOR_VERSION,
        },
        "environment": {
            "app_env": settings.app_env.value,
            "log_level": settings.log_level.value,
        },
        "database": {
            "engine": pg.engine_driver,
            "pgvector_extension": pg.pgvector_extension,
            "embedding_dimension": pg.embedding_dimension,
            "products_table": pg.products_table,
            "embedding_column": pg.embedding_column,
            "hnsw_index_name": pg.hnsw_index_name,
            "pgvector_operator_class": pg.pgvector_operator_class,
            "vector_catalog_schema_version": pg.vector_catalog_schema_version,
            "configuration": {
                "primary_env": "DATABASE_URL",
                "component_fields_env_prefix": "PRODUCTIQ_DATABASE_*",
                "host": db.host,
                "port": db.port,
                "name": db.database_name,
                "user": db.database_user,
                "redacted_url": db.redacted_url,
            },
        },
        "artifacts": {
            "paths": public_artifact_paths(paths),
            "integrity": [
                {
                    "role": item.role,
                    "checksum_sha256": item.checksum_sha256,
                    "checksum_algorithm": item.checksum_algorithm,
                    "schema_version": item.schema_version,
                    "note": item.note,
                }
                for item in integrity
            ],
        },
        "configuration": {
            "app_env": "APP_ENV",
            "database_url": "DATABASE_URL",
            "artifact_env_vars": [
                "PRODUCTIQ_PROCESSED_CATALOG_PATH",
                "PRODUCTIQ_BM25_ARTIFACT_PATH",
                "PRODUCTIQ_EMBEDDINGS_ARTIFACT_PATH",
                "PRODUCTIQ_MODEL_ARTIFACTS_DIR",
            ],
            "cors": "PRODUCTIQ_CORS_ALLOWED_ORIGINS",
        },
        "health": {
            "liveness": "/health",
            "readiness": "/ready",
        },
    }


def write_deployment_manifest(
    path: Path | None = None,
    *,
    settings: Settings,
    serving: ServingConfig | None = None,
) -> Path:
    """Write manifest JSON to ``resources/deployment`` (no secrets)."""
    target = path or DEFAULT_MANIFEST_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    document = build_deployment_manifest(settings=settings, serving=serving)
    target.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    return target


__all__ = [
    "DEFAULT_MANIFEST_PATH",
    "MANIFEST_VERSION",
    "build_deployment_manifest",
    "write_deployment_manifest",
]
