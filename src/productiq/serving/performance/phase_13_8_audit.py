"""Phase 13.8 final performance system audit (Phase 13.8.9)."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from productiq.serving.performance.artifact_integrity import (
    ArtifactIntegrityReport,
    audit_benchmark_artifact_integrity,
)
from productiq.serving.performance.evidence_analysis import (
    build_serving_performance_evidence_report,
)

SEARCH_SERVING_PERFORMANCE_BENCHMARK_ENV = "PRODUCTIQ_SEARCH_SERVING_PERFORMANCE_BENCHMARK"
RECOMMENDATION_SERVING_PERFORMANCE_BENCHMARK_ENV = (
    "PRODUCTIQ_RECOMMENDATION_SERVING_PERFORMANCE_BENCHMARK"
)
PRODUCT_SERVING_PERFORMANCE_BENCHMARK_ENV = "PRODUCTIQ_PRODUCT_SERVING_PERFORMANCE_BENCHMARK"
SERVING_CONCURRENCY_BENCHMARK_ENV = "PRODUCTIQ_SERVING_CONCURRENCY_BENCHMARK"

PHASE_13_8_AUDIT_VERSION = "1.0.0"
PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_AUDIT_JSON = (
    PROJECT_ROOT / "resources" / "benchmark" / "serving_performance_phase_13_8_final_audit.json"
)
DEFAULT_AUDIT_MD = (
    PROJECT_ROOT / "resources" / "benchmark" / "serving_performance_phase_13_8_final_audit.md"
)


class ImplementationStatus(StrEnum):
    IMPLEMENTED = "implemented"
    MEASURED = "measured"
    PENDING = "pending"


class SubPhaseAuditRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    phase_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    implementation: ImplementationStatus
    measurement: ImplementationStatus
    notes: str | None = None


class PerformanceEnvironmentFlag(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    prerequisites: tuple[str, ...] = ()
    when_disabled: str = Field(min_length=1)


class Phase138FinalAuditReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    audit_version: str = Field(default=PHASE_13_8_AUDIT_VERSION, min_length=1)
    generated_at_utc: datetime
    phase_scope: str = Field(min_length=1)
    sub_phases: tuple[SubPhaseAuditRecord, ...]
    environment_flags: tuple[PerformanceEnvironmentFlag, ...]
    import_safety_summary: str = Field(min_length=1)
    test_isolation_summary: str = Field(min_length=1)
    determinism_summary: str = Field(min_length=1)
    artifact_integrity: ArtifactIntegrityReport
    baseline_safety_summary: str = Field(min_length=1)
    concurrency_safety_summary: str = Field(min_length=1)
    production_behavior_change_summary: str = Field(min_length=1)
    metric_semantics_summary: str = Field(min_length=1)
    optimization_status: str = Field(min_length=1)
    stage_measurements_status: str = Field(min_length=1)
    outstanding_measurement_gaps: tuple[str, ...]
    limitations: tuple[str, ...]
    reproducibility: tuple[str, ...]


def performance_environment_flags() -> tuple[PerformanceEnvironmentFlag, ...]:
    return (
        PerformanceEnvironmentFlag(
            name=SEARCH_SERVING_PERFORMANCE_BENCHMARK_ENV,
            purpose="Opt-in gate for 13.8.3 production search serving benchmark pytest/script.",
            prerequisites=(
                "PRODUCTIQ_RUN_INTEGRATION_TESTS=1",
                "PRODUCTIQ_PRODUCTION_RETRIEVAL_SMOKE=1",
                "PostgreSQL/pgvector retrieval stack",
            ),
            when_disabled="Production search benchmark tests skip; no artifacts written.",
        ),
        PerformanceEnvironmentFlag(
            name=RECOMMENDATION_SERVING_PERFORMANCE_BENCHMARK_ENV,
            purpose="Opt-in gate for 13.8.4 production recommendation serving benchmark.",
            prerequisites=(
                "PRODUCTIQ_RUN_INTEGRATION_TESTS=1",
                "PRODUCTIQ_PRODUCTION_RETRIEVAL_SMOKE=1",
                "Catalog seeds for recommendation workloads",
            ),
            when_disabled="Production recommendation benchmark tests skip.",
        ),
        PerformanceEnvironmentFlag(
            name=PRODUCT_SERVING_PERFORMANCE_BENCHMARK_ENV,
            purpose="Opt-in gate for 13.8.5 production product serving benchmark.",
            prerequisites=("resources/processed/product_catalog.parquet",),
            when_disabled="Production product benchmark tests skip.",
        ),
        PerformanceEnvironmentFlag(
            name=SERVING_CONCURRENCY_BENCHMARK_ENV,
            purpose="Opt-in gate for 13.8.6 concurrency sweeps (product measured; search/rec pending).",
            prerequisites=(
                "Endpoint-specific: product parquet and/or retrieval stack for search/rec",
            ),
            when_disabled="Production concurrency benchmark tests skip.",
        ),
        PerformanceEnvironmentFlag(
            name="PRODUCTIQ_RUN_INTEGRATION_TESTS",
            purpose="Shared prerequisite for PostgreSQL-backed integration and retrieval benchmarks.",
            prerequisites=("PostgreSQL products table with embeddings",),
            when_disabled="Integration and retrieval-gated benchmarks skip or fail closed in tests.",
        ),
        PerformanceEnvironmentFlag(
            name="PRODUCTIQ_PRODUCTION_RETRIEVAL_SMOKE",
            purpose="Production retrieval smoke prerequisite for search/recommendation serving benchmarks.",
            prerequisites=("BM25/HNSW or documented fallback per live_dependencies",),
            when_disabled="Search/recommendation production serving benchmarks skip in pytest.",
        ),
    )


def sub_phase_audit_records() -> tuple[SubPhaseAuditRecord, ...]:
    evidence = build_serving_performance_evidence_report()
    search_measured = (
        ImplementationStatus.MEASURED
        if evidence.inventory.search_serving_run_json_count > 0
        else ImplementationStatus.PENDING
    )
    rec_measured = (
        ImplementationStatus.MEASURED
        if evidence.inventory.recommendation_serving_run_json_count > 0
        else ImplementationStatus.PENDING
    )
    product_measured = (
        ImplementationStatus.MEASURED
        if evidence.inventory.product_serving_run_json_count > 0
        else ImplementationStatus.PENDING
    )
    concurrency_measured = (
        ImplementationStatus.MEASURED
        if evidence.inventory.concurrency_sweep_json_count > 0
        else ImplementationStatus.PENDING
    )
    return (
        SubPhaseAuditRecord(
            phase_id="13.8.1",
            title="Serving performance contract",
            implementation=ImplementationStatus.IMPLEMENTED,
            measurement=ImplementationStatus.IMPLEMENTED,
            notes="Schema + workloads; validated by contract tests.",
        ),
        SubPhaseAuditRecord(
            phase_id="13.8.2",
            title="Benchmark harness",
            implementation=ImplementationStatus.IMPLEMENTED,
            measurement=ImplementationStatus.IMPLEMENTED,
            notes="Warmups excluded from latency samples; throughput uses wall clock.",
        ),
        SubPhaseAuditRecord(
            phase_id="13.8.3",
            title="Search serving benchmark",
            implementation=ImplementationStatus.IMPLEMENTED,
            measurement=search_measured,
            notes="Production measurements pending when opt-in benchmark not run.",
        ),
        SubPhaseAuditRecord(
            phase_id="13.8.4",
            title="Recommendation serving benchmark",
            implementation=ImplementationStatus.IMPLEMENTED,
            measurement=rec_measured,
        ),
        SubPhaseAuditRecord(
            phase_id="13.8.5",
            title="Product serving benchmark",
            implementation=ImplementationStatus.IMPLEMENTED,
            measurement=product_measured,
        ),
        SubPhaseAuditRecord(
            phase_id="13.8.6",
            title="Concurrency sweeps",
            implementation=ImplementationStatus.IMPLEMENTED,
            measurement=concurrency_measured,
            notes="Product sweeps measured locally; search/recommendation concurrency pending.",
        ),
        SubPhaseAuditRecord(
            phase_id="13.8.7",
            title="Baseline & regression",
            implementation=ImplementationStatus.IMPLEMENTED,
            measurement=ImplementationStatus.IMPLEMENTED,
            notes="Framework only; pinned baseline JSON optional.",
        ),
        SubPhaseAuditRecord(
            phase_id="13.8.8",
            title="Evidence-based optimization",
            implementation=ImplementationStatus.IMPLEMENTED,
            measurement=ImplementationStatus.IMPLEMENTED,
            notes="No production optimization retained.",
        ),
        SubPhaseAuditRecord(
            phase_id="13.8.9",
            title="Hardening & final audit",
            implementation=ImplementationStatus.IMPLEMENTED,
            measurement=ImplementationStatus.IMPLEMENTED,
        ),
    )


def build_phase_13_8_final_audit_report(
    *,
    benchmark_root: Path | None = None,
) -> Phase138FinalAuditReport:
    integrity = audit_benchmark_artifact_integrity(benchmark_root=benchmark_root)
    evidence = build_serving_performance_evidence_report(benchmark_root=benchmark_root)

    gaps: list[str] = []
    if evidence.inventory.search_serving_run_json_count == 0:
        gaps.append("Search production serving benchmark artifacts missing (13.8.3).")
    if evidence.inventory.recommendation_serving_run_json_count == 0:
        gaps.append("Recommendation production serving benchmark artifacts missing (13.8.4).")
    gaps.append("Search/recommendation concurrency production sweeps pending (13.8.6).")
    gaps.append("stage_measurements empty on existing serving benchmark runs.")

    return Phase138FinalAuditReport(
        generated_at_utc=datetime.now(tz=UTC),
        phase_scope="Phase 13.8 serving performance measurement, baseline/regression, and evidence workflow.",
        sub_phases=sub_phase_audit_records(),
        environment_flags=performance_environment_flags(),
        import_safety_summary=(
            "FastAPI create_app and serving services do not import productiq.serving.performance; "
            "benchmark code lives under serving/performance/ and scripts/ only."
        ),
        test_isolation_summary=(
            "Default pytest suites skip production benchmarks unless explicit PRODUCTIQ_* flags; "
            "PostgreSQL/BM25/embeddings not required for standard serving/api/recommendation tests."
        ),
        determinism_summary=(
            "Workload catalogs, configurations, JSON round-trips, baseline identity, provenance checks, "
            "regression comparison, and evidence reports are covered by unit tests; timestamps/run IDs "
            "remain non-deterministic by design."
        ),
        artifact_integrity=integrity,
        baseline_safety_summary=(
            "Baselines require explicit pin; overwrite=False by default; identity + provenance matching; "
            "BASELINE_NOT_FOUND without nearest-match; no fabricated search/rec baselines."
        ),
        concurrency_safety_summary=(
            "Concurrency benchmark does not modify production code for thread safety; error accounting "
            "enforced in runner; warmups excluded from measured iterations."
        ),
        production_behavior_change_summary=(
            "Phase 13.8.8 retained no optimization; performance infrastructure is isolated from "
            "search/retrieval/ranking/recommendation/product serving semantics."
        ),
        metric_semantics_summary=(
            "Latency percentiles via compute_latency_statistics_ms; throughput = success_count/wall_seconds; "
            "relative_pct_delta returns None for zero baseline; missing throughput not coerced to zero in comparison."
        ),
        optimization_status="No production optimization retained in 13.8.8 or 13.8.9.",
        stage_measurements_status="Empty on checked-in serving benchmark artifacts.",
        outstanding_measurement_gaps=tuple(gaps),
        limitations=(
            "Audit reflects repository state at generation time; pending measurements are not marked complete.",
            "Product API benchmark latency includes HTTP/TestClient stack.",
            "No statistical significance testing in Phase 13.8.",
        ),
        reproducibility=(
            "Standard tests: python -m pytest tests/serving tests/api tests/recommendation -q",
            "Benchmark tests: tests/serving/test_serving_performance_*.py (synthetic) and opt-in production modules",
            "Compare: scripts/compare_serving_performance.py",
            "Evidence: scripts/analyze_serving_performance_evidence.py",
            "Regenerate audit: scripts/run_serving_performance_phase_13_8_audit.py",
        ),
    )


def render_phase_13_8_final_audit_markdown(report: Phase138FinalAuditReport) -> str:
    lines: list[str] = [
        "# Phase 13.8 — Serving performance final audit",
        "",
        f"- audit_version: `{report.audit_version}`",
        f"- generated_at_utc: `{report.generated_at_utc.isoformat()}`",
        "",
        "## Scope",
        "",
        report.phase_scope,
        "",
        "## Sub-phases (implementation vs measurement)",
        "",
        "| ID | Title | Implementation | Measurement | Notes |",
        "|----|-------|----------------|-------------|-------|",
    ]
    for sub in report.sub_phases:
        notes = (sub.notes or "").replace("|", "\\|")
        lines.append(
            f"| {sub.phase_id} | {sub.title} | {sub.implementation.value} | "
            f"{sub.measurement.value} | {notes} |",
        )

    lines.extend(["", "## Environment flags", ""])
    for flag in report.environment_flags:
        lines.append(f"### `{flag.name}`")
        lines.append(f"- purpose: {flag.purpose}")
        if flag.prerequisites:
            lines.append("- prerequisites:")
            for pre in flag.prerequisites:
                lines.append(f"  - {pre}")
        lines.append(f"- when disabled: {flag.when_disabled}")
        lines.append("")

    ai = report.artifact_integrity
    lines.extend(
        [
            "## Artifact integrity",
            "",
            f"- run results validated: `{ai.run_results_validated}` failed: `{ai.run_results_failed}`",
            f"- sweeps validated: `{ai.sweeps_validated}` failed: `{ai.sweeps_failed}`",
            f"- checksum verifications: `{ai.checksum_verifications}` mismatches: `{ai.checksum_mismatches}`",
        ],
    )
    if ai.issues:
        lines.append("- issues:")
        for issue in ai.issues[:20]:
            lines.append(f"  - `{issue.path}` [{issue.code}]: {issue.message}")
        if len(ai.issues) > 20:
            lines.append(f"  - ... and {len(ai.issues) - 20} more")

    sections = (
        ("Import safety", report.import_safety_summary),
        ("Test isolation", report.test_isolation_summary),
        ("Determinism", report.determinism_summary),
        ("Baseline safety", report.baseline_safety_summary),
        ("Concurrency safety", report.concurrency_safety_summary),
        ("Production behavior", report.production_behavior_change_summary),
        ("Metric semantics", report.metric_semantics_summary),
        ("Optimization", report.optimization_status),
        ("Stage measurements", report.stage_measurements_status),
    )
    for title, body in sections:
        lines.extend(["", f"## {title}", "", body])

    if report.outstanding_measurement_gaps:
        lines.extend(["", "## Outstanding measurement gaps", ""])
        for gap in report.outstanding_measurement_gaps:
            lines.append(f"- {gap}")

    if report.limitations:
        lines.extend(["", "## Limitations", ""])
        for lim in report.limitations:
            lines.append(f"- {lim}")

    lines.extend(["", "## Reproducibility", ""])
    for step in report.reproducibility:
        lines.append(f"- {step}")
    lines.append("")
    return "\n".join(lines)


def write_phase_13_8_final_audit_artifacts(
    *,
    benchmark_root: Path | None = None,
    json_path: Path | None = None,
    markdown_path: Path | None = None,
) -> Phase138FinalAuditReport:
    report = build_phase_13_8_final_audit_report(benchmark_root=benchmark_root)
    json_target = json_path or DEFAULT_AUDIT_JSON
    md_target = markdown_path or DEFAULT_AUDIT_MD
    json_target.parent.mkdir(parents=True, exist_ok=True)
    json_target.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    md_target.write_text(render_phase_13_8_final_audit_markdown(report), encoding="utf-8")
    return report


__all__ = [
    "DEFAULT_AUDIT_JSON",
    "DEFAULT_AUDIT_MD",
    "PHASE_13_8_AUDIT_VERSION",
    "ImplementationStatus",
    "PerformanceEnvironmentFlag",
    "Phase138FinalAuditReport",
    "SubPhaseAuditRecord",
    "build_phase_13_8_final_audit_report",
    "performance_environment_flags",
    "render_phase_13_8_final_audit_markdown",
    "write_phase_13_8_final_audit_artifacts",
]
