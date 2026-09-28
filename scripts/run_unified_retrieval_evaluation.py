"""Run unified retrieval evaluation from existing artifacts (Phase 4.18)."""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from productiq.retrieval.evaluation.unified_reporting import (
    build_catalog_from_evaluation_dir,
    write_unified_evaluation_artifacts,
)


def main() -> int:
    eval_dir = _ROOT / "resources" / "evaluation"
    catalog = build_catalog_from_evaluation_dir(eval_dir)
    paths = write_unified_evaluation_artifacts(eval_dir, catalog)
    for path in paths:
        print(f"Wrote {path}", flush=True)
    for evaluation in catalog.evaluations:
        print(
            evaluation.lineage.system_name,
            f"MRR={evaluation.aggregate.mrr:.4f}",
            f"P@10={evaluation.aggregate.mean_precision_at_k[10]:.4f}",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
