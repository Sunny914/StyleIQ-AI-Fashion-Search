"""Orchestrate Phase 12.5 baseline search evaluation runs."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Literal

from productiq.exceptions.base import RetrievalError
from productiq.retrieval.evaluation.search_evaluation.baseline_artifact import (
    build_baseline_run_artifact,
    default_baseline_metric_configuration,
    write_baseline_run_artifact,
)
from productiq.retrieval.evaluation.search_evaluation.baseline_executors import (
    Bm25BaselineSetup,
    SemanticBaselineSetup,
    create_bm25_baseline_setup,
    create_rrf_baseline_setup,
    create_semantic_baseline_setup,
)
from productiq.retrieval.evaluation.search_evaluation.baseline_schema import (
    SEARCH_BASELINE_BM25_RUN_FILENAME,
    SEARCH_BASELINE_RRF_RUN_FILENAME,
    SEARCH_BASELINE_SEMANTIC_RUN_FILENAME,
    SUPPORTED_SEARCH_BASELINE_VARIANTS,
)
from productiq.retrieval.evaluation.search_evaluation.baseline_variants import (
    bm25_retrieval_provenance,
    bm25_search_evaluation_variant,
    rrf_retrieval_provenance,
    rrf_search_evaluation_variant,
    semantic_retrieval_provenance,
    semantic_search_evaluation_variant,
)
from productiq.retrieval.evaluation.search_evaluation.benchmark_artifact_schema import (
    SEARCH_BENCHMARK_FILENAME,
    SEARCH_BENCHMARK_NAME,
    SEARCH_BENCHMARK_VERSION,
)
from productiq.retrieval.evaluation.search_evaluation.benchmark_loader import (
    build_search_evaluation_request,
    load_search_evaluation_benchmark,
)
from productiq.retrieval.evaluation.search_evaluation.benchmark_schema import (
    SearchEvaluationBenchmark,
)
from productiq.retrieval.evaluation.search_evaluation.request_schema import (
    SearchEvaluationRequest,
    SearchMetricConfiguration,
)
from productiq.retrieval.evaluation.search_evaluation.result_schema import (
    SearchVariantEvaluationResult,
)
from productiq.retrieval.evaluation.search_evaluation.runner import (
    SearchEvaluationVariantExecutor,
    run_search_evaluation,
)
from productiq.retrieval.rrf_config import RRFConfig


def _lexical_phase48_historical_reference(repo_root: Path) -> dict[str, Any] | None:
    path = repo_root / "resources" / "evaluation" / "lexical_retrieval_benchmark_v1_run.json"
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return None
    aggregate = payload.get("aggregate")
    index_mode = payload.get("index_mode")
    if not isinstance(aggregate, dict):
        return None
    return {
        "source_artifact": "resources/evaluation/lexical_retrieval_benchmark_v1_run.json",
        "phase": "4.8_lexical_retrieval_benchmark_v1",
        "note": (
            "Historical Phase 4.8 BM25 metrics on lexical_retrieval_benchmark_v1 (binary labels). "
            "Not a winner declaration; configuration and benchmark envelope differ from Phase 12.5."
        ),
        "index_mode": index_mode,
        "aggregate_metrics": aggregate,
    }


def evaluate_search_baseline(
    request: SearchEvaluationRequest,
    executor: SearchEvaluationVariantExecutor,
    *,
    retrieval_provenance: dict[str, Any],
    runtime_metadata: dict[str, Any] | None = None,
    historical_reference: dict[str, Any] | None = None,
) -> tuple[SearchVariantEvaluationResult, dict[str, Any]]:
    """Run Phase 12.4 runner and wrap results in a Phase 12.5 baseline artifact dict."""
    started = time.perf_counter()
    result = run_search_evaluation(request, executor)
    duration = time.perf_counter() - started
    runtime = dict(runtime_metadata or {})
    runtime["evaluation_duration_seconds"] = duration
    runtime["successful_query_count"] = len(result.per_query)
    runtime["query_count"] = len(request.benchmark.queries)
    artifact = build_baseline_run_artifact(
        result,
        retrieval_provenance=retrieval_provenance,
        runtime_metadata=runtime,
        historical_reference=historical_reference,
    )
    return result, artifact


def baseline_run_artifact_path(
    repo_root: Path,
    variant: Literal["bm25", "semantic", "rrf"],
) -> Path:
    filenames = {
        "bm25": SEARCH_BASELINE_BM25_RUN_FILENAME,
        "semantic": SEARCH_BASELINE_SEMANTIC_RUN_FILENAME,
        "rrf": SEARCH_BASELINE_RRF_RUN_FILENAME,
    }
    return repo_root / "resources" / "evaluation" / filenames[variant]


def load_canonical_search_benchmark(repo_root: Path) -> SearchEvaluationBenchmark:
    path = repo_root / "resources" / "evaluation" / SEARCH_BENCHMARK_FILENAME
    benchmark = load_search_evaluation_benchmark(path)
    if benchmark.benchmark_name != SEARCH_BENCHMARK_NAME or benchmark.benchmark_version != SEARCH_BENCHMARK_VERSION:
        msg = (
            f"unexpected canonical benchmark identity: "
            f"{benchmark.benchmark_name!r} v{benchmark.benchmark_version!r}"
        )
        raise RetrievalError(msg)
    return benchmark


def run_bm25_search_baseline(
    repo_root: Path,
    *,
    metric_configuration: SearchMetricConfiguration | None = None,
) -> dict[str, Any]:
    root = Path(repo_root)
    benchmark = load_canonical_search_benchmark(root)
    config = metric_configuration or default_baseline_metric_configuration()
    setup = create_bm25_baseline_setup(root)
    variant = bm25_search_evaluation_variant(
        index_mode=setup.index_mode,
        bm25_manifest=setup.bm25_manifest,
    )
    request = build_search_evaluation_request(benchmark, variant, metric_configuration=config)
    provenance = bm25_retrieval_provenance(
        index_mode=setup.index_mode,
        bm25_manifest=setup.bm25_manifest,
        index_path=str(setup.index_path.relative_to(root)).replace("\\", "/"),
    )
    runtime = {"bm25_index_mode": setup.index_mode}
    _, artifact = evaluate_search_baseline(
        request,
        setup.executor,
        retrieval_provenance=provenance,
        runtime_metadata=runtime,
        historical_reference=_lexical_phase48_historical_reference(root),
    )
    out_path = baseline_run_artifact_path(root, "bm25")
    write_baseline_run_artifact(out_path, artifact)
    artifact["artifact_path"] = str(out_path.relative_to(root)).replace("\\", "/")
    return artifact


def _load_semantic_phase414_reference(repo_root: Path) -> dict[str, Any] | None:
    path = repo_root / "resources" / "evaluation" / "semantic_retrieval_benchmark_v1_run.json"
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return None
    aggregate = payload.get("aggregate")
    if not isinstance(aggregate, dict):
        return None
    return {
        "source_artifact": "resources/evaluation/semantic_retrieval_benchmark_v1_run.json",
        "phase": "4.14_semantic_retrieval_benchmark_v1",
        "note": (
            "Historical Phase 4.14 semantic metrics on semantic_retrieval_benchmark_v1. "
            "Descriptive reference only; not a hybrid score or winner."
        ),
        "aggregate_metrics": aggregate,
    }


def run_semantic_search_baseline(
    repo_root: Path,
    *,
    engine: Any,
    encoder: Any,
    metric_configuration: SearchMetricConfiguration | None = None,
) -> dict[str, Any]:
    root = Path(repo_root)
    benchmark = load_canonical_search_benchmark(root)
    config = metric_configuration or default_baseline_metric_configuration()
    setup = create_semantic_baseline_setup(root, engine=engine, encoder=encoder)
    variant = semantic_search_evaluation_variant(vector_index_manifest=setup.vector_index_manifest)
    request = build_search_evaluation_request(benchmark, variant, metric_configuration=config)
    provenance = semantic_retrieval_provenance(vector_index_manifest=setup.vector_index_manifest)
    _, artifact = evaluate_search_baseline(
        request,
        setup.executor,
        retrieval_provenance=provenance,
        runtime_metadata={},
        historical_reference=_load_semantic_phase414_reference(root),
    )
    out_path = baseline_run_artifact_path(root, "semantic")
    write_baseline_run_artifact(out_path, artifact)
    artifact["artifact_path"] = str(out_path.relative_to(root)).replace("\\", "/")
    return artifact


def _load_rrf_phase416_reference(repo_root: Path) -> dict[str, Any] | None:
    path = repo_root / "resources" / "evaluation" / "hybrid_rrf_benchmark_v1_run.json"
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return None
    aggregate = payload.get("aggregate")
    if not isinstance(aggregate, dict):
        return None
    return {
        "source_artifact": "resources/evaluation/hybrid_rrf_benchmark_v1_run.json",
        "phase": "4.16_hybrid_rrf_benchmark_v1",
        "note": (
            "Historical Phase 4.16 RRF run artifact. Descriptive reference only."
        ),
        "aggregate_metrics": aggregate,
    }


def run_rrf_search_baseline(
    repo_root: Path,
    *,
    bm25_setup: Bm25BaselineSetup,
    semantic_setup: SemanticBaselineSetup,
    metric_configuration: SearchMetricConfiguration | None = None,
    rrf_config: RRFConfig | None = None,
) -> dict[str, Any]:
    root = Path(repo_root)
    benchmark = load_canonical_search_benchmark(root)
    config = metric_configuration or default_baseline_metric_configuration()
    rrf_setup = create_rrf_baseline_setup(
        root,
        bm25_retriever=bm25_setup.executor.retriever,
        semantic_retriever=semantic_setup.semantic_retriever,
        bm25_index_mode=bm25_setup.index_mode,
        rrf_config=rrf_config,
    )
    variant = rrf_search_evaluation_variant(
        bm25_manifest=rrf_setup.bm25_manifest,
        vector_index_manifest=rrf_setup.vector_index_manifest,
        rank_constant=rrf_setup.rrf_config.rank_constant,
        bm25_index_mode=rrf_setup.bm25_index_mode,
    )
    request = build_search_evaluation_request(benchmark, variant, metric_configuration=config)
    provenance = rrf_retrieval_provenance(
        bm25_manifest=rrf_setup.bm25_manifest,
        vector_index_manifest=rrf_setup.vector_index_manifest,
        rank_constant=rrf_setup.rrf_config.rank_constant,
        bm25_index_mode=rrf_setup.bm25_index_mode,
    )
    _, artifact = evaluate_search_baseline(
        request,
        rrf_setup.executor,
        retrieval_provenance=provenance,
        runtime_metadata={"bm25_index_mode": rrf_setup.bm25_index_mode},
        historical_reference=_load_rrf_phase416_reference(root),
    )
    out_path = baseline_run_artifact_path(root, "rrf")
    write_baseline_run_artifact(out_path, artifact)
    artifact["artifact_path"] = str(out_path.relative_to(root)).replace("\\", "/")
    return artifact


__all__ = [
    "SUPPORTED_SEARCH_BASELINE_VARIANTS",
    "baseline_run_artifact_path",
    "evaluate_search_baseline",
    "load_canonical_search_benchmark",
    "run_bm25_search_baseline",
    "run_rrf_search_baseline",
    "run_semantic_search_baseline",
]
