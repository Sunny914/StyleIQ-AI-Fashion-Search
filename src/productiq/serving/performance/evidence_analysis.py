"""Evidence-based serving performance analysis (Phase 13.8.8)."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from productiq.serving.performance.schema import ServingBenchmarkRunResult

PERFORMANCE_EVIDENCE_ANALYSIS_VERSION = "1.0.0"

PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_BENCHMARK_ROOT = PROJECT_ROOT / "resources" / "benchmark"

REFERENCE_PRODUCT_BASELINE_RUN_ID = "7c60fd3a-f882-4cca-a7a9-1e189976e7cf"


class EvidenceClassification(StrEnum):
    OBSERVED = "observed"
    POTENTIAL = "potential"
    UNKNOWN = "unknown"


class PerformanceEvidenceFinding(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    classification: EvidenceClassification
    subsystem: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    evidence_artifact: str | None = None
    notes: str | None = None


class OptimizationCandidateRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    subsystem: str = Field(min_length=1)
    observed_measurement: str | None = None
    evidence_artifact: str | None = None
    suspected_bottleneck: str | None = None
    hypothesis: str | None = None
    expected_effect: str | None = None
    risk: str | None = None
    validation_benchmark: str | None = None
    blocked: bool = True
    blocker_reason: str | None = None


class BenchmarkArtifactInventory(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    search_serving_run_json_count: int = Field(ge=0)
    recommendation_serving_run_json_count: int = Field(ge=0)
    product_serving_run_json_count: int = Field(ge=0)
    concurrency_sweep_json_count: int = Field(ge=0)
    pinned_baseline_json_count: int = Field(ge=0)


class ServingPerformanceEvidenceReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_version: str = Field(default=PERFORMANCE_EVIDENCE_ANALYSIS_VERSION, min_length=1)
    generated_at_utc: datetime
    inventory: BenchmarkArtifactInventory
    findings: tuple[PerformanceEvidenceFinding, ...]
    optimization_candidates: tuple[OptimizationCandidateRecord, ...]
    optimization_selected: str | None = None
    optimization_retained: bool = False
    optimization_blockers: tuple[str, ...] = ()
    limitations: tuple[str, ...] = (
        "Findings are classified; potential items are not treated as proven bottlenecks.",
        "No production serving code was changed in Phase 13.8.8 due to missing or inconclusive evidence.",
        "Stage instrumentation remains empty for existing serving benchmarks.",
    )


def _count_glob(directory: Path, pattern: str) -> int:
    if not directory.is_dir():
        return 0
    return sum(1 for path in directory.glob(pattern) if path.is_file())


def inventory_benchmark_artifacts(
    *,
    benchmark_root: Path | None = None,
) -> BenchmarkArtifactInventory:
    root = benchmark_root or DEFAULT_BENCHMARK_ROOT
    baselines_root = root / "baselines"
    baseline_count = 0
    if baselines_root.is_dir():
        for category in ("search", "recommendation", "product", "concurrency"):
            baseline_count += _count_glob(baselines_root / category, "*.json")
    return BenchmarkArtifactInventory(
        search_serving_run_json_count=_count_glob(root / "search_serving", "*_api_*.json")
        + _count_glob(root / "search_serving", "*_service_*.json"),
        recommendation_serving_run_json_count=_count_glob(
            root / "recommendation_serving",
            "*_api_*.json",
        )
        + _count_glob(root / "recommendation_serving", "*_service_*.json"),
        product_serving_run_json_count=_count_glob(root / "product_serving", "*.json"),
        concurrency_sweep_json_count=_count_glob(root / "concurrency", "*_sweep.json"),
        pinned_baseline_json_count=baseline_count,
    )


def _try_load_product_reference_run(
    benchmark_root: Path,
) -> ServingBenchmarkRunResult | None:
    rel = (
        f"product_serving/*_{REFERENCE_PRODUCT_BASELINE_RUN_ID}_service_"
        "product_serving_existing_v1.json"
    )
    matches = sorted(benchmark_root.glob(rel))
    if not matches:
        return None
    return ServingBenchmarkRunResult.model_validate_json(matches[-1].read_text(encoding="utf-8"))


def _static_findings(
    inventory: BenchmarkArtifactInventory,
    reference_service_run: ServingBenchmarkRunResult | None,
) -> tuple[PerformanceEvidenceFinding, ...]:
    findings: list[PerformanceEvidenceFinding] = []

    if inventory.product_serving_run_json_count > 0:
        artifact = (
            f"resources/benchmark/product_serving/*_{REFERENCE_PRODUCT_BASELINE_RUN_ID}_*"
        )
        findings.append(
            PerformanceEvidenceFinding(
                classification=EvidenceClassification.OBSERVED,
                subsystem="product",
                statement=(
                    "Production product serving benchmarks exist with processed Parquet catalog "
                    "and in-memory O(1) lookup after one-time initialization."
                ),
                evidence_artifact=artifact,
            ),
        )
        if reference_service_run is not None and reference_service_run.latency is not None:
            lat = reference_service_run.latency
            findings.append(
                PerformanceEvidenceFinding(
                    classification=EvidenceClassification.OBSERVED,
                    subsystem="product",
                    statement=(
                        f"Service-boundary product_serving_existing_v1 mean latency is "
                        f"{lat.mean_ms:.4f} ms (run {REFERENCE_PRODUCT_BASELINE_RUN_ID})."
                    ),
                    evidence_artifact=(
                        "resources/benchmark/product_serving/"
                        f"*_{REFERENCE_PRODUCT_BASELINE_RUN_ID}_service_product_serving_existing_v1.json"
                    ),
                ),
            )
    else:
        findings.append(
            PerformanceEvidenceFinding(
                classification=EvidenceClassification.UNKNOWN,
                subsystem="product",
                statement="No product serving benchmark JSON artifacts were found.",
            ),
        )

    if inventory.concurrency_sweep_json_count > 0:
        findings.append(
            PerformanceEvidenceFinding(
                classification=EvidenceClassification.OBSERVED,
                subsystem="product",
                statement="Product concurrency sweeps (API and service) exist under resources/benchmark/concurrency/.",
                evidence_artifact="resources/benchmark/concurrency/*_production-product-concurrency-*_sweep.json",
            ),
        )

    if inventory.search_serving_run_json_count == 0:
        findings.append(
            PerformanceEvidenceFinding(
                classification=EvidenceClassification.UNKNOWN,
                subsystem="search",
                statement="Search production serving latency baseline is not present in artifact storage.",
                evidence_artifact="resources/benchmark/search_serving/README.md",
                notes="Run 13.8.3 opt-in production benchmark before evidence-based search optimization.",
            ),
        )

    if inventory.recommendation_serving_run_json_count == 0:
        findings.append(
            PerformanceEvidenceFinding(
                classification=EvidenceClassification.UNKNOWN,
                subsystem="recommendation",
                statement="Recommendation production serving latency baseline is not present in artifact storage.",
                evidence_artifact="resources/benchmark/recommendation_serving/README.md",
                notes="Run 13.8.4 opt-in production benchmark before evidence-based recommendation optimization.",
            ),
        )

    findings.append(
        PerformanceEvidenceFinding(
            classification=EvidenceClassification.POTENTIAL,
            subsystem="recommendation",
            statement=(
                "Attribute candidate generation iterates list_catalog_products() per request in code; "
                "this is architectural behavior, not a proven dominant latency source without serving benchmarks."
            ),
            evidence_artifact="src/productiq/recommendation/generators/attribute.py",
        ),
    )

    findings.append(
        PerformanceEvidenceFinding(
            classification=EvidenceClassification.UNKNOWN,
            subsystem="serving",
            statement="Per-stage serving latency (stage_measurements) is empty for existing 13.8.3–13.8.6 runs.",
            notes="Cannot attribute API vs service gaps to specific internal stages from current artifacts.",
        ),
    )

    if reference_service_run is not None:
        api_pattern = (
            f"resources/benchmark/product_serving/*_{REFERENCE_PRODUCT_BASELINE_RUN_ID}_"
            "api_product_serving_existing_v1.json"
        )
        findings.append(
            PerformanceEvidenceFinding(
                classification=EvidenceClassification.OBSERVED,
                subsystem="product",
                statement=(
                    "Product API boundary latency is orders of magnitude higher than service boundary "
                    "for the same workload in run "
                    f"{REFERENCE_PRODUCT_BASELINE_RUN_ID}; empty stage_measurements prevent "
                    "attributing the gap to a specific production component."
                ),
                evidence_artifact=api_pattern,
            ),
        )

    return tuple(findings)


def _optimization_candidates(
    inventory: BenchmarkArtifactInventory,
    reference_service_run: ServingBenchmarkRunResult | None,
) -> tuple[OptimizationCandidateRecord, ...]:
    candidates: list[OptimizationCandidateRecord] = []

    service_mean: str | None = None
    if reference_service_run is not None and reference_service_run.latency is not None:
        service_mean = f"{reference_service_run.latency.mean_ms:.4f} ms service mean (c=1)"

    candidates.append(
        OptimizationCandidateRecord(
            subsystem="product",
            observed_measurement=service_mean,
            evidence_artifact=f"resources/benchmark/product_serving/*_{REFERENCE_PRODUCT_BASELINE_RUN_ID}_*",
            suspected_bottleneck="Catalog lookup after Parquet index build",
            hypothesis="Further optimize in-memory product lookup",
            expected_effect="Lower service latency",
            risk="Micro-optimization with no measurable gain; correctness regressions in mapping",
            validation_benchmark="13.8.5 product_serving_existing_v1 service boundary",
            blocked=True,
            blocker_reason=(
                "OBSERVED service latency is already sub-millisecond; no benchmark evidence "
                "identifies catalog lookup as a bottleneck."
            ),
        ),
    )

    candidates.append(
        OptimizationCandidateRecord(
            subsystem="recommendation",
            suspected_bottleneck="Full-catalog scan during attribute generation",
            hypothesis="Index or cache derived attribute structures to avoid per-request catalog scans",
            expected_effect="Lower recommendation serving latency",
            risk="Memory footprint; stale derived data if catalog updates",
            validation_benchmark="13.8.4 recommendation serving production benchmark (same workload/boundary)",
            blocked=True,
            blocker_reason=(
                "No 13.8.4 production serving benchmark artifacts; potential bottleneck only — "
                "not proven dominant."
            ),
        ),
    )

    candidates.append(
        OptimizationCandidateRecord(
            subsystem="search",
            suspected_bottleneck="Retrieval/ranking path under HTTP serving",
            hypothesis="Tune retrieval or ranking data access after bottleneck identification",
            expected_effect="Lower search serving latency",
            risk="Relevance or determinism regressions",
            validation_benchmark="13.8.3 search serving production benchmark",
            blocked=True,
            blocker_reason="No 13.8.3 production serving benchmark artifacts.",
        ),
    )

    candidates.append(
        OptimizationCandidateRecord(
            subsystem="product",
            observed_measurement="API mean ~5.57 ms vs service mean ~0.005 ms (same run, c=1)",
            evidence_artifact=f"resources/benchmark/product_serving/*_{REFERENCE_PRODUCT_BASELINE_RUN_ID}_*",
            suspected_bottleneck="HTTP/FastAPI/TestClient stack vs service method",
            hypothesis="Optimize API serialization or routing",
            expected_effect="Lower API latency",
            risk="API contract changes; unmeasured on real HTTP clients",
            validation_benchmark="13.8.5 API boundary + stage instrumentation (not available)",
            blocked=True,
            blocker_reason=(
                "Gap is OBSERVED but not decomposed; optimizing production catalog/service code "
                "would not address the measured API boundary without stage evidence."
            ),
        ),
    )

    if inventory.search_serving_run_json_count == 0 or inventory.recommendation_serving_run_json_count == 0:
        _ = candidates  # blockers already recorded per candidate

    return tuple(candidates)


def build_serving_performance_evidence_report(
    *,
    benchmark_root: Path | None = None,
) -> ServingPerformanceEvidenceReport:
    root = benchmark_root or DEFAULT_BENCHMARK_ROOT
    inventory = inventory_benchmark_artifacts(benchmark_root=root)
    reference = _try_load_product_reference_run(root)
    findings = _static_findings(inventory, reference)
    candidates = _optimization_candidates(inventory, reference)

    blockers: list[str] = []
    if inventory.search_serving_run_json_count == 0:
        blockers.append("search: missing 13.8.3 production serving benchmark artifacts")
    if inventory.recommendation_serving_run_json_count == 0:
        blockers.append("recommendation: missing 13.8.4 production serving benchmark artifacts")
    blockers.append(
        "product: sub-millisecond service latency observed — no evidence-backed production change selected",
    )
    blockers.append(
        "serving: stage_measurements empty — cannot target internal optimizations from benchmarks",
    )

    return ServingPerformanceEvidenceReport(
        generated_at_utc=datetime.now(tz=UTC),
        inventory=inventory,
        findings=findings,
        optimization_candidates=candidates,
        optimization_selected=None,
        optimization_retained=False,
        optimization_blockers=tuple(blockers),
    )


def render_evidence_report_markdown(report: ServingPerformanceEvidenceReport) -> str:
    lines: list[str] = [
        "# Serving performance evidence report (Phase 13.8.8)",
        "",
        f"- generated_at_utc: `{report.generated_at_utc.isoformat()}`",
        f"- optimization_selected: `{report.optimization_selected}`",
        f"- optimization_retained: `{report.optimization_retained}`",
        "",
        "## Artifact inventory",
        "",
        f"- search serving run JSON: `{report.inventory.search_serving_run_json_count}`",
        f"- recommendation serving run JSON: `{report.inventory.recommendation_serving_run_json_count}`",
        f"- product serving JSON: `{report.inventory.product_serving_run_json_count}`",
        f"- concurrency sweeps: `{report.inventory.concurrency_sweep_json_count}`",
        f"- pinned baselines: `{report.inventory.pinned_baseline_json_count}`",
        "",
        "## Findings",
        "",
    ]
    for item in report.findings:
        lines.append(f"### {item.classification.value.upper()} — {item.subsystem}")
        lines.append(f"- {item.statement}")
        if item.evidence_artifact:
            lines.append(f"- artifact: `{item.evidence_artifact}`")
        if item.notes:
            lines.append(f"- notes: {item.notes}")
        lines.append("")

    lines.append("## Optimization candidates (not ranked)")
    lines.append("")
    for cand in report.optimization_candidates:
        status = "BLOCKED" if cand.blocked else "OPEN"
        lines.append(f"### {cand.subsystem} [{status}]")
        if cand.observed_measurement:
            lines.append(f"- observed: {cand.observed_measurement}")
        if cand.hypothesis:
            lines.append(f"- hypothesis: {cand.hypothesis}")
        if cand.blocker_reason:
            lines.append(f"- blocker: {cand.blocker_reason}")
        lines.append("")

    if report.optimization_blockers:
        lines.append("## Optimization blockers")
        lines.append("")
        for blocker in report.optimization_blockers:
            lines.append(f"- {blocker}")
        lines.append("")

    if report.limitations:
        lines.append("## Limitations")
        lines.append("")
        for lim in report.limitations:
            lines.append(f"- {lim}")

    lines.append("")
    return "\n".join(lines)


__all__ = [
    "PERFORMANCE_EVIDENCE_ANALYSIS_VERSION",
    "BenchmarkArtifactInventory",
    "EvidenceClassification",
    "OptimizationCandidateRecord",
    "PerformanceEvidenceFinding",
    "REFERENCE_PRODUCT_BASELINE_RUN_ID",
    "ServingPerformanceEvidenceReport",
    "build_serving_performance_evidence_report",
    "inventory_benchmark_artifacts",
    "render_evidence_report_markdown",
]
