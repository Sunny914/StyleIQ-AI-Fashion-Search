"""Run retrieval failure analysis from existing benchmark artifacts (Phase 4.17)."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from productiq.retrieval.evaluation.failure_reporting import (
    run_failure_analysis_from_evaluation_dir,
    write_failure_analysis_artifacts,
)


def main() -> int:
    eval_dir = _ROOT / "resources" / "evaluation"
    parquet_path = _ROOT / "resources" / "processed" / "product_representations.parquet"
    report, summary = run_failure_analysis_from_evaluation_dir(
        eval_dir,
        representation_parquet_path=parquet_path,
    )
    paths = write_failure_analysis_artifacts(eval_dir, report, summary)
    for path in paths:
        print(f"Wrote {path}", flush=True)
    print(
        f"Analyzed {report.query_count} queries, "
        f"{report.judged_relevant_product_count} judged relevant products",
        flush=True,
    )
    print(summary.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
