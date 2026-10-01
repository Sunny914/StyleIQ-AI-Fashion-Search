#!/usr/bin/env python3
"""Compare serving performance benchmark runs against a pinned baseline (Phase 13.8.7)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pydantic import ValidationError as PydanticValidationError

from productiq.exceptions.base import ValidationError
from productiq.serving.performance.baseline_schema import PerformanceThresholdPolicy
from productiq.serving.performance.baseline_storage import (
    category_for_endpoint,
    load_baseline_record,
    load_run_result_artifact,
)
from productiq.serving.performance.regression_engine import compare_to_baseline_record
from productiq.serving.performance.regression_report import (
    render_performance_comparison_report_markdown,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare a current serving benchmark artifact to a pinned baseline.",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        required=True,
        help="Path to a pinned baseline JSON (ServingPerformanceBaselineRecord).",
    )
    parser.add_argument(
        "--current",
        type=Path,
        required=True,
        help="Path to a current run JSON (ServingBenchmarkRunResult).",
    )
    parser.add_argument(
        "--benchmark-boundary",
        choices=("api", "service"),
        default=None,
        help="Required when current artifact is from a CONCURRENCY sweep (api vs service).",
    )
    parser.add_argument(
        "--threshold-policy",
        type=Path,
        default=None,
        help="Optional JSON file for PerformanceThresholdPolicy.",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="Optional path to write PerformanceComparisonReport JSON.",
    )
    parser.add_argument(
        "--markdown-out",
        type=Path,
        default=None,
        help="Optional path to write Markdown report.",
    )
    parser.add_argument(
        "--fail-on-incompatible",
        action="store_true",
        help="Exit code 1 when provenance/identity is incompatible or baseline missing.",
    )
    parser.add_argument(
        "--fail-on-regression-flags",
        action="store_true",
        help="Exit code 2 when threshold policy is set and regression_flags is non-empty.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        baseline = load_baseline_record(args.baseline)
        current = load_run_result_artifact(args.current)
    except (ValidationError, PydanticValidationError, OSError, ValueError) as exc:
        print(f"error loading artifacts: {exc}", file=sys.stderr)
        return 1

    policy: PerformanceThresholdPolicy | None = None
    if args.threshold_policy is not None:
        try:
            policy = PerformanceThresholdPolicy.model_validate_json(
                args.threshold_policy.read_text(encoding="utf-8"),
            )
        except (PydanticValidationError, OSError, ValueError) as exc:
            print(f"error loading threshold policy: {exc}", file=sys.stderr)
            return 1

    _ = category_for_endpoint(current.configuration.endpoint.value)

    report = compare_to_baseline_record(
        baseline,
        current,
        benchmark_boundary=args.benchmark_boundary,
        threshold_policy=policy,
    )

    markdown = render_performance_comparison_report_markdown(report)
    print(markdown)

    if args.json_out is not None:
        args.json_out.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    if args.markdown_out is not None:
        args.markdown_out.write_text(markdown, encoding="utf-8")

    if args.fail_on_incompatible and not report.compatibility.compatible:
        return 1
    if (
        args.fail_on_regression_flags
        and policy is not None
        and report.regression_flags
    ):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
