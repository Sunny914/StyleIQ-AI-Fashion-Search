"""Deterministic Markdown rendering for search evaluation reports (Phase 12.10)."""

from __future__ import annotations

from productiq.retrieval.evaluation.search_evaluation.reporting.report_schema import (
    SearchEvaluationReport,
)


def render_search_evaluation_report_markdown(report: SearchEvaluationReport) -> str:
    lines: list[str] = [
        "# ProductIQ Search Evaluation Report",
        "",
        "## Evaluation Identity",
        f"- report_name: {report.metadata.report_name}",
        f"- report_version: {report.metadata.report_version}",
        f"- evaluation_contract_version: {report.metadata.evaluation_contract_version}",
        "",
        "## Benchmark",
        f"- benchmark_name: {report.benchmark.benchmark_name}",
        f"- benchmark_version: {report.benchmark.benchmark_version}",
        f"- benchmark_artifact_path: {report.benchmark.benchmark_artifact_path}",
        f"- query_count: {report.benchmark.query_count}",
        "",
        "## Evaluation Configuration",
        f"- execution_top_k: {report.configuration.execution_top_k}",
        f"- evaluation_top_k: {report.configuration.evaluation_top_k}",
        f"- min_relevant_grade: {report.configuration.metric_configuration.min_relevant_grade}",
        f"- k_values: {list(report.configuration.metric_configuration.k_values)}",
        "",
        "## Variant Results",
    ]
    for variant in report.variant_summaries:
        lines.append(f"### {variant.variant_name} ({variant.source_phase})")
        if variant.retrieval_index_mode:
            lines.append(f"- retrieval_index_mode: {variant.retrieval_index_mode}")
        lines.append(f"- query_count: {variant.query_count}")
        mrr = next((row for row in variant.metrics if row.metric_name == "mrr"), None)
        if mrr is not None:
            lines.append(f"- mrr: {mrr.value}")
        p10 = next(
            (row for row in variant.metrics if row.metric_name == "precision_at_k" and row.k == 10),
            None,
        )
        if p10 is not None:
            lines.append(f"- precision_at_10: {p10.value}")
        lines.append("")

    lines.extend(["## Pairwise Comparisons", ""])
    for row in report.pairwise_comparisons:
        if row.k is None:
            label = row.metric_name
        else:
            label = f"{row.metric_name}@{row.k}"
        lines.append(
            f"- [{row.comparison_source}] {row.reference_variant_name} -> "
            f"{row.candidate_variant_name} {label}: "
            f"ref={row.reference_value} cand={row.candidate_value} delta={row.absolute_delta}"
        )
    lines.append("")

    lines.extend(["## Failure Analysis", ""])
    if report.failure_analysis is None:
        lines.append("_No 12.8 failure analysis artifact loaded._")
    else:
        lines.append(f"- failure_record_count: {report.failure_analysis.failure_record_count}")
        for pattern_row in report.failure_analysis.retrieval_pattern_rows:
            lines.append(f"- retrieval_pattern {pattern_row.pattern}: {pattern_row.product_count}")
    lines.append("")

    lines.extend(["## Statistical Analysis", ""])
    if report.statistical_analysis is None:
        lines.append("_No 12.9 statistical analysis artifact loaded._")
    else:
        for stat_row in report.statistical_analysis.comparisons:
            if stat_row.metric_name == "mrr":
                metric_label = "mrr"
            else:
                metric_label = f"{stat_row.metric_name}@{stat_row.k}"
            lines.append(
                f"- {stat_row.reference_variant_name} -> {stat_row.candidate_variant_name} "
                f"{metric_label}: delta={stat_row.observed_delta} p={stat_row.p_value}"
            )
    lines.append("")

    lines.extend(["## Reproducibility", ""])
    manifest = report.reproducibility
    lines.append(f"- catalog_artifact: {manifest.catalog_artifact}")
    lines.append(f"- source_representation_checksum: {manifest.source_representation_checksum}")
    lines.append(f"- ltr_artifact_path: {manifest.ltr_artifact_path}")
    lines.append(f"- ltr_artifact_present: {manifest.ltr_artifact_present}")
    for name, mode in manifest.retrieval_index_modes:
        if mode:
            lines.append(f"- retrieval_index_mode[{name}]: {mode}")
    lines.append("")

    lines.extend(["## Limitations", ""])
    for item in report.limitations:
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


__all__ = ["render_search_evaluation_report_markdown"]
