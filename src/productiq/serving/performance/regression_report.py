"""Markdown rendering for performance comparison reports (Phase 13.8.7)."""

from __future__ import annotations

from productiq.serving.performance.baseline_schema import PerformanceComparisonReport


def render_performance_comparison_report_markdown(report: PerformanceComparisonReport) -> str:
    lines: list[str] = [
        "# Serving performance comparison report",
        "",
        f"**Contract:** `{report.contract_version}`",
        "",
        "## Benchmark identity",
        "",
        f"- endpoint: `{report.identity.endpoint.value}`",
        f"- workload_id: `{report.identity.workload_id}`",
        f"- benchmark_boundary: `{report.identity.benchmark_boundary}`",
        f"- concurrency: `{report.identity.concurrency}`",
        f"- warmups: `{report.identity.warmups}`",
        f"- iterations: `{report.identity.iterations}`",
        "",
        "## Compatibility",
        "",
        f"- status: `{report.compatibility.status.value}`",
        f"- compatible: `{report.compatibility.compatible}`",
    ]
    if report.compatibility.mismatches:
        lines.append("- mismatches:")
        for item in report.compatibility.mismatches:
            lines.append(f"  - `{item}`")
    if report.compatibility.provenance_differences:
        lines.append("- provenance differences (informational):")
        for item in report.compatibility.provenance_differences:
            lines.append(f"  - {item}")

    lines.extend(
        [
            "",
            "## Run metadata",
            "",
            f"- baseline_run_id: `{report.baseline_run_id}`",
            f"- current_run_id: `{report.current_run_id}`",
            f"- baseline_pinned_at_utc: `{report.baseline_pinned_at_utc}`",
            f"- current_recorded_at_utc: `{report.current_recorded_at_utc}`",
        ],
    )

    if report.latency_comparison is not None:
        lat = report.latency_comparison
        lines.extend(["", "## Latency deltas", ""])
        for name in ("min_ms", "mean_ms", "p50_ms", "p95_ms", "p99_ms", "max_ms"):
            abs_delta = lat.absolute_delta_ms.get(name)
            rel_delta = lat.relative_delta_pct.get(name)
            lines.append(
                f"- `{name}`: absolute_ms={abs_delta}, relative_pct={rel_delta}",
            )

    if report.throughput_comparison is not None:
        tp = report.throughput_comparison
        lines.extend(
            [
                "",
                "## Throughput",
                "",
                f"- baseline_rps: `{tp.baseline_rps}`",
                f"- current_rps: `{tp.current_rps}`",
                f"- absolute_delta_rps: `{tp.absolute_delta_rps}`",
                f"- relative_delta_pct: `{tp.relative_delta_pct}`",
            ],
        )

    if report.reliability_comparison is not None:
        rel = report.reliability_comparison
        lines.extend(
            [
                "",
                "## Reliability",
                "",
                f"- success_count_delta: `{rel.success_count_delta}`",
                f"- error_count_delta: `{rel.error_count_delta}`",
                f"- error_rate_delta: `{rel.error_rate_delta}`",
            ],
        )

    if report.threshold_policy is not None:
        lines.extend(["", "## Threshold policy", "", f"```json\n{report.threshold_policy.model_dump_json(indent=2)}\n```"])

    if report.threshold_observations:
        lines.extend(["", "## Threshold observations", ""])
        for obs in report.threshold_observations:
            flag = "REGRESSION_FLAG" if obs.regression_flag else "OBSERVATION"
            lines.append(f"- **{flag}** `{obs.metric}`: {obs.observation}")
            lines.append(
                f"  baseline={obs.baseline_value}, current={obs.current_value}, "
                f"absolute_delta={obs.absolute_delta}, relative_delta_pct={obs.relative_delta_pct}, "
                f"threshold={obs.threshold}",
            )

    if report.regression_flags:
        lines.extend(["", "## Regression flags", ""])
        for flag in report.regression_flags:
            lines.append(f"- `{flag}`")

    if report.limitations:
        lines.extend(["", "## Limitations", ""])
        for item in report.limitations:
            lines.append(f"- {item}")

    lines.append("")
    return "\n".join(lines)


__all__ = ["render_performance_comparison_report_markdown"]
