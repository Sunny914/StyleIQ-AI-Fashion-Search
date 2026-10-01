"""Tests for Phase 13.8.8 evidence-based performance analysis."""

from __future__ import annotations

import json
from pathlib import Path

from productiq.serving.performance.evidence_analysis import (
    EvidenceClassification,
    build_serving_performance_evidence_report,
    inventory_benchmark_artifacts,
    render_evidence_report_markdown,
)


def test_inventory_on_repository_benchmark_root() -> None:
    inventory = inventory_benchmark_artifacts()
    assert inventory.product_serving_run_json_count > 0
    assert inventory.concurrency_sweep_json_count > 0
    assert inventory.search_serving_run_json_count == 0
    assert inventory.recommendation_serving_run_json_count == 0


def test_report_marks_search_and_recommendation_unknown() -> None:
    report = build_serving_performance_evidence_report()
    search_unknown = [
        f
        for f in report.findings
        if f.subsystem == "search" and f.classification is EvidenceClassification.UNKNOWN
    ]
    rec_unknown = [
        f
        for f in report.findings
        if f.subsystem == "recommendation" and f.classification is EvidenceClassification.UNKNOWN
    ]
    assert search_unknown
    assert rec_unknown


def test_no_optimization_selected() -> None:
    report = build_serving_performance_evidence_report()
    assert report.optimization_selected is None
    assert report.optimization_retained is False
    assert report.optimization_blockers


def test_recommendation_scan_is_potential_not_observed_bottleneck() -> None:
    report = build_serving_performance_evidence_report()
    potential = [
        f
        for f in report.findings
        if f.subsystem == "recommendation" and f.classification is EvidenceClassification.POTENTIAL
    ]
    assert potential
    assert "not a proven dominant" in potential[0].statement.lower() or "not a proven" in potential[0].statement


def test_all_candidates_blocked_without_production_evidence() -> None:
    report = build_serving_performance_evidence_report()
    assert report.optimization_candidates
    assert all(c.blocked for c in report.optimization_candidates)


def test_report_json_round_trip_deterministic_structure() -> None:
    report = build_serving_performance_evidence_report()
    payload = json.loads(report.model_dump_json())
    restored = type(report).model_validate(payload)
    assert restored.inventory == report.inventory
    assert len(restored.findings) == len(report.findings)


def test_markdown_render_is_stable_for_fixed_report() -> None:
    report = build_serving_performance_evidence_report()
    assert "Optimization blockers" in render_evidence_report_markdown(report)


def test_empty_benchmark_root_inventory(tmp_path: Path) -> None:
    inventory = inventory_benchmark_artifacts(benchmark_root=tmp_path)
    assert inventory.product_serving_run_json_count == 0
