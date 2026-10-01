"""Tests for Phase 13.8.9 performance hardening and final audit."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from productiq.serving.performance.artifact_integrity import audit_benchmark_artifact_integrity
from productiq.serving.performance.comparison import relative_pct_delta
from productiq.serving.performance.evidence_analysis import (
    build_serving_performance_evidence_report,
)
from productiq.serving.performance.phase_13_8_audit import (
    ImplementationStatus,
    build_phase_13_8_final_audit_report,
    performance_environment_flags,
    write_phase_13_8_final_audit_artifacts,
)
from productiq.serving.performance.workloads import DEFAULT_SERVING_PERFORMANCE_WORKLOADS

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PRODUCTION_MODULE_PATHS = (
    PROJECT_ROOT / "src" / "productiq" / "api" / "app.py",
    PROJECT_ROOT / "src" / "productiq" / "api" / "services" / "application_wiring.py",
    PROJECT_ROOT / "src" / "productiq" / "serving" / "search_service.py",
    PROJECT_ROOT / "src" / "productiq" / "serving" / "product_service.py",
)


@pytest.mark.parametrize("path", PRODUCTION_MODULE_PATHS)
def test_production_modules_do_not_import_performance_package(path: Path) -> None:
    assert path.is_file(), f"missing module under test: {path}"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "serving.performance" not in alias.name
        if isinstance(node, ast.ImportFrom) and node.module:
            assert "serving.performance" not in node.module


def test_create_app_import_does_not_load_performance_package() -> None:
    import sys

    from productiq.api.app import create_app
    from tests.api.fakes import RecordingSearchService

    before = set(sys.modules)
    create_app(search_service=RecordingSearchService())
    new_perf = [
        name
        for name in sys.modules
        if name.startswith("productiq.serving.performance") and name not in before
    ]
    assert not new_perf


def test_environment_flag_inventory_complete() -> None:
    flags = performance_environment_flags()
    names = {flag.name for flag in flags}
    assert "PRODUCTIQ_SEARCH_SERVING_PERFORMANCE_BENCHMARK" in names
    assert "PRODUCTIQ_RECOMMENDATION_SERVING_PERFORMANCE_BENCHMARK" in names
    assert "PRODUCTIQ_PRODUCT_SERVING_PERFORMANCE_BENCHMARK" in names
    assert "PRODUCTIQ_SERVING_CONCURRENCY_BENCHMARK" in names


def test_final_audit_marks_search_and_rec_measurement_pending() -> None:
    report = build_phase_13_8_final_audit_report()
    by_id = {sub.phase_id: sub for sub in report.sub_phases}
    assert by_id["13.8.3"].measurement is ImplementationStatus.PENDING
    assert by_id["13.8.4"].measurement is ImplementationStatus.PENDING
    assert by_id["13.8.5"].measurement is ImplementationStatus.MEASURED


def test_artifact_integrity_validates_product_runs() -> None:
    integrity = audit_benchmark_artifact_integrity()
    assert integrity.run_results_validated > 0
    assert integrity.run_results_failed == 0
    assert integrity.checksum_mismatches == 0


def test_relative_delta_zero_baseline_is_none_not_zero() -> None:
    assert relative_pct_delta(0.0, 10.0) is None


def test_workload_catalog_deterministic_ordering() -> None:
    ids_a = [w.workload_id for w in DEFAULT_SERVING_PERFORMANCE_WORKLOADS]
    ids_b = [w.workload_id for w in DEFAULT_SERVING_PERFORMANCE_WORKLOADS]
    assert ids_a == ids_b
    assert len(ids_a) == len(set(ids_a))


def test_evidence_and_audit_reports_round_trip_json() -> None:
    audit = build_phase_13_8_final_audit_report()
    restored = type(audit).model_validate(json.loads(audit.model_dump_json()))
    assert restored.audit_version == audit.audit_version
    assert len(restored.sub_phases) == len(audit.sub_phases)
    evidence = build_serving_performance_evidence_report()
    assert evidence.optimization_retained is False


def test_write_audit_artifacts_to_tmp_path(tmp_path: Path) -> None:
    report = write_phase_13_8_final_audit_artifacts(
        json_path=tmp_path / "audit.json",
        markdown_path=tmp_path / "audit.md",
    )
    assert (tmp_path / "audit.json").is_file()
    assert (tmp_path / "audit.md").is_file()
    assert report.optimization_status
