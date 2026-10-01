"""Phase 14B runtime artifact and database deployment contract tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from productiq.api.app import create_app
from productiq.config.database_runtime import (
    postgres_runtime_contract,
    summarize_database_configuration,
)
from productiq.config.deployment_manifest import MANIFEST_VERSION, build_deployment_manifest
from productiq.config.runtime_artifacts import (
    resolve_bm25_index_path,
    resolve_runtime_artifact_paths,
)
from productiq.config.runtime_validation import (
    load_optional_manifest_metadata,
    public_artifact_paths,
    require_runtime_artifacts,
    validate_runtime_artifacts,
)
from productiq.config.settings import Settings
from productiq.exceptions.base import ConfigurationError
from productiq.retrieval.index_schema import BM25_LEXICAL_INDEX_FILENAME
from productiq.serving.errors import ApiErrorCode, map_exception_to_api_error
from tests.api.fakes import RecordingSearchService


def test_resolve_processed_catalog_from_settings() -> None:
    settings = Settings(_env_file=None, processed_catalog_path="data/catalog.parquet")
    paths = resolve_runtime_artifact_paths(settings)
    assert paths.processed_catalog == Path("data/catalog.parquet")


def test_resolve_bm25_legacy_layout_next_to_catalog(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    catalog = Path("product_catalog.parquet")
    catalog.write_bytes(b"stub")
    bm25 = Path(BM25_LEXICAL_INDEX_FILENAME)
    bm25.write_bytes(b"stub")
    settings = Settings(
        _env_file=None,
        processed_catalog_path=catalog,
        bm25_artifact_path=Path("bm25"),
    )
    assert resolve_bm25_index_path(settings) == bm25


def test_validate_missing_catalog_reports_safe_message(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    settings = Settings(
        _env_file=None,
        processed_catalog_path=Path("data/missing.parquet"),
    )
    results = validate_runtime_artifacts(settings, require_roles=frozenset({"processed_catalog"}))
    assert len(results) == 1
    assert not results[0].ok
    assert "Processed product catalog" in results[0].message
    assert str(tmp_path) not in results[0].message


def test_require_runtime_artifacts_raises_configuration_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    settings = Settings(
        _env_file=None,
        processed_catalog_path=Path("missing.parquet"),
    )
    with pytest.raises(ConfigurationError, match="Runtime deployment artifacts"):
        require_runtime_artifacts(settings, require_roles=frozenset({"processed_catalog"}))


def test_configuration_error_maps_without_path_leak(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    settings = Settings(
        _env_file=None,
        processed_catalog_path=Path("secret/path.parquet"),
    )
    try:
        require_runtime_artifacts(settings, require_roles=frozenset({"processed_catalog"}))
    except ConfigurationError as exc:
        body = map_exception_to_api_error(exc, request_id="rid-1")
    else:
        raise AssertionError("expected ConfigurationError")
    assert body.code is ApiErrorCode.CONFIGURATION_ERROR
    assert "secret" not in body.message.lower()
    assert "path.parquet" not in body.message


def test_database_configuration_summary_redacts_secrets() -> None:
    settings = Settings(
        _env_file=None,
        database_url_override="postgresql://user:topsecret@db.example.com:5432/productiq",
    )
    summary = summarize_database_configuration(settings)
    assert "topsecret" not in summary.redacted_url


def test_postgres_runtime_contract_pgvector_dimension() -> None:
    contract = postgres_runtime_contract()
    assert contract.pgvector_extension == "vector"
    assert contract.embedding_dimension == 384
    assert contract.products_table == "products"
    assert contract.embedding_column == "embedding"


def test_deployment_manifest_structure() -> None:
    settings = Settings(_env_file=None)
    manifest = build_deployment_manifest(settings=settings)
    assert manifest["manifest_version"] == MANIFEST_VERSION
    assert manifest["application"]["api_entrypoint"] == "productiq.api.app:create_app"
    assert manifest["database"]["embedding_dimension"] == 384
    assert manifest["health"]["liveness"] == "/health"
    assert "topsecret" not in json.dumps(manifest)


def test_load_manifest_metadata_when_present(tmp_path: Path) -> None:
    manifest = tmp_path / "demo.manifest.json"
    manifest.write_text(
        json.dumps({"checksum": "abc", "checksum_algorithm": "sha256", "schema_version": "1.0.0"}),
        encoding="utf-8",
    )
    meta = load_optional_manifest_metadata(manifest)
    assert meta is not None
    assert meta.checksum_sha256 == "abc"


def test_create_app_import_does_not_connect_to_postgres(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_engine(*args: object, **kwargs: object) -> None:
        raise AssertionError("database engine must not be created at import/create_app")

    monkeypatch.setattr("productiq.database.engine.create_engine", fail_engine)
    app = create_app(
        search_service=RecordingSearchService(),
        app_settings=Settings(_env_file=None, app_env="production"),
    )
    assert app.state.runtime_artifact_paths.processed_catalog.name.endswith(".parquet")


def test_public_artifact_paths_are_strings() -> None:
    paths = resolve_runtime_artifact_paths(Settings(_env_file=None))
    public = public_artifact_paths(paths)
    assert all(isinstance(value, str) for value in public.values())
