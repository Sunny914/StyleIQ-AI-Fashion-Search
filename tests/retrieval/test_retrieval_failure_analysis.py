"""Tests for Phase 4.17 retrieval failure analysis."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from productiq.retrieval.evaluation.failure_analysis_schema import (
    RELEVANCE_JUDGMENT_JUDGED_RELEVANT,
    Bm25ObservedClassification,
    FailureAnalysisLineage,
    RetrievalPatternClassification,
    SemanticObservedClassification,
)
from productiq.retrieval.evaluation.failure_analyzer import (
    QueryRetrievalArtifactSlice,
    analyze_query_product,
    analyze_retrieval_failures,
    build_rank_lookup,
    derive_retrieval_pattern_classifications,
)
from productiq.retrieval.evaluation.failure_reporting import (
    build_summary_report,
    run_failure_analysis_from_evaluation_dir,
    write_failure_analysis_artifacts,
)
from productiq.retrieval.rrf_fusion import compute_rrf_score


def _lineage(**overrides: object) -> FailureAnalysisLineage:
    base: dict[str, object] = {
        "analysis_version": "1.0.0",
        "lexical_benchmark_name": "productiq_lexical_retrieval_v1",
        "lexical_benchmark_version": "1.0.0",
        "lexical_run_artifact": "lexical_retrieval_benchmark_v1_run.json",
        "lexical_index_mode": "full_persisted_index",
        "semantic_run_artifact": "semantic_retrieval_benchmark_v1_run.json",
        "semantic_analysis_artifact": "semantic_retrieval_benchmark_v1_analysis.jsonl",
        "hybrid_rrf_run_artifact": "hybrid_rrf_benchmark_v1_run.json",
        "rrf_bm25_index_mode": "benchmark_scoped_slice_4912_docs",
        "rrf_rank_constant": 60,
        "retrieval_top_k": 50,
        "incomplete_judgment_warning": "incomplete judgments",
        "rrf_scoped_bm25_limitation": "scoped rrf",
        "bm25_native_score_limitation": "no bm25 scores in artifact",
    }
    base.update(overrides)
    return FailureAnalysisLineage(**base)  # type: ignore[arg-type]


def _slice(
    *,
    bm25: tuple[str, ...] = (),
    semantic: tuple[str, ...] = (),
    rrf: tuple[str, ...] = (),
    judged: tuple[str, ...] = ("P1",),
    semantic_scores: dict[str, float] | None = None,
) -> QueryRetrievalArtifactSlice:
    return QueryRetrievalArtifactSlice(
        query_id="q_test",
        query_text="test query",
        category="brand_product",
        judged_relevant_product_ids=judged,
        bm25_retrieved_product_ids=bm25,
        semantic_retrieved_product_ids=semantic,
        rrf_retrieved_product_ids=rrf,
        semantic_native_scores=semantic_scores or {},
    )


def test_bm25_only_pattern() -> None:
    patterns = derive_retrieval_pattern_classifications(
        bm25_rank=3,
        semantic_rank=None,
        rrf_rank=2,
        retrieval_top_k=50,
    )
    assert RetrievalPatternClassification.BM25_ONLY in patterns
    assert RetrievalPatternClassification.NOT_RETRIEVED_BY_EITHER not in patterns


def test_semantic_only_pattern() -> None:
    patterns = derive_retrieval_pattern_classifications(
        bm25_rank=None,
        semantic_rank=4,
        rrf_rank=3,
        retrieval_top_k=50,
    )
    assert RetrievalPatternClassification.SEMANTIC_ONLY in patterns


def test_both_pattern() -> None:
    patterns = derive_retrieval_pattern_classifications(
        bm25_rank=1,
        semantic_rank=2,
        rrf_rank=1,
        retrieval_top_k=50,
    )
    assert RetrievalPatternClassification.RETRIEVED_BY_BOTH in patterns


def test_neither_pattern() -> None:
    patterns = derive_retrieval_pattern_classifications(
        bm25_rank=None,
        semantic_rank=None,
        rrf_rank=None,
        retrieval_top_k=50,
    )
    assert patterns == (RetrievalPatternClassification.NOT_RETRIEVED_BY_EITHER,)


def test_depth_limited_when_rank_beyond_10() -> None:
    patterns = derive_retrieval_pattern_classifications(
        bm25_rank=15,
        semantic_rank=None,
        rrf_rank=12,
        retrieval_top_k=50,
    )
    assert RetrievalPatternClassification.DEPTH_LIMITED in patterns


def test_rrf_low_rank_when_worse_than_source() -> None:
    patterns = derive_retrieval_pattern_classifications(
        bm25_rank=2,
        semantic_rank=3,
        rrf_rank=10,
        retrieval_top_k=50,
    )
    assert RetrievalPatternClassification.RETRIEVED_BUT_RRF_LOW_RANK in patterns


def test_duplicate_product_ids_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        build_rank_lookup(("A", "A"), source_label="BM25")


def test_empty_retrieval_lists() -> None:
    query = _slice(bm25=(), semantic=(), rrf=(), judged=("MISSING",))
    row = analyze_query_product(
        query,
        "MISSING",
        retrieval_top_k=50,
        rrf_rank_constant=60,
        catalog_row=None,
        include_representation_evidence=False,
    )
    assert row.bm25_observed_classification is Bm25ObservedClassification.NOT_RETRIEVED_BY_BM25
    assert row.semantic_observed_classification is SemanticObservedClassification.NOT_RETRIEVED_BY_SEMANTIC
    assert not row.rrf.retrieved
    assert row.rrf.fusion_score is None


def test_native_semantic_score_preserved() -> None:
    query = _slice(
        semantic=("P1",),
        bm25=("P1",),
        rrf=("P1",),
        semantic_scores={"P1": 0.77},
    )
    row = analyze_query_product(
        query,
        "P1",
        retrieval_top_k=50,
        rrf_rank_constant=60,
        catalog_row=None,
        include_representation_evidence=False,
    )
    assert row.semantic.native_score == pytest.approx(0.77)
    assert row.rrf.vector_native_score == pytest.approx(0.77)
    assert row.bm25.native_score is None


def test_fusion_score_from_ranks() -> None:
    query = _slice(bm25=("P1",), semantic=("P1",), rrf=("P1",))
    row = analyze_query_product(
        query,
        "P1",
        retrieval_top_k=50,
        rrf_rank_constant=60,
        catalog_row=None,
        include_representation_evidence=False,
    )
    expected = compute_rrf_score(bm25_rank=1, vector_rank=1, rank_constant=60)
    assert row.rrf.fusion_score == pytest.approx(expected)


def test_judged_relevance_label_only() -> None:
    row = analyze_query_product(
        _slice(judged=("P1",), bm25=("P1",)),
        "P1",
        retrieval_top_k=50,
        rrf_rank_constant=60,
        catalog_row=None,
        include_representation_evidence=False,
    )
    assert row.relevance_judgment == RELEVANCE_JUDGMENT_JUDGED_RELEVANT


def test_deterministic_ordering() -> None:
    query = _slice(
        judged=("B", "A"),
        bm25=("A", "B"),
        semantic=("B", "A"),
        rrf=("A", "B"),
    )
    report = analyze_retrieval_failures(
        productiq_version="0.1.0",
        lineage=_lineage(),
        queries=(query,),
        include_representation_evidence=False,
    )
    assert [row.product_id for row in report.diagnostics] == ["A", "B"]


def test_depth_flags_at_k() -> None:
    query = _slice(bm25=("X",) + tuple(f"F{i}" for i in range(19)), semantic=(), rrf=())
    row = analyze_query_product(
        query,
        "X",
        retrieval_top_k=50,
        rrf_rank_constant=60,
        catalog_row=None,
        include_representation_evidence=False,
    )
    assert row.bm25.rank == 1
    assert row.bm25.depth.at_1
    assert row.bm25.depth.at_50


def test_representation_evidence_for_review_candidate() -> None:
    catalog_row = {
        "brand": "Nike",
        "category_gender": "Men",
        "product_text": "desc",
        "lexical_text": "lex",
        "semantic_text": "sem",
    }
    query = _slice(judged=("P1",))
    row = analyze_query_product(
        query,
        "P1",
        retrieval_top_k=50,
        rrf_rank_constant=60,
        catalog_row=catalog_row,
        include_representation_evidence=True,
    )
    assert row.representation_review_candidate
    assert row.representation_evidence is not None
    assert row.representation_evidence.fields["brand"] == "Nike"
    assert row.representation_evidence.fields["description"] == "desc"


def test_integration_against_recorded_artifacts(tmp_path: Path) -> None:
    repo_eval = Path("resources/evaluation")
    if not (repo_eval / "hybrid_rrf_benchmark_v1_run.json").is_file():
        pytest.skip("benchmark artifacts not present")
    report, summary = run_failure_analysis_from_evaluation_dir(
        repo_eval,
        representation_parquet_path=Path("resources/processed/product_representations.parquet"),
    )
    assert report.query_count == 10
    assert report.judged_relevant_product_count == 44
    assert len(report.diagnostics) == 44
    assert summary.judged_relevant_product_count == 44
    assert "NOT_RETRIEVED_BY_EITHER" in summary.retrieval_pattern_counts


def test_write_artifacts_round_trip(tmp_path: Path) -> None:
    query = _slice(judged=("P1",), bm25=("P1",), semantic=("P1",), rrf=("P1",))
    report = analyze_retrieval_failures(
        productiq_version="0.1.0",
        lineage=_lineage(),
        queries=(query,),
        include_representation_evidence=False,
    )
    summary = build_summary_report(report)
    json_path, jsonl_path, summary_path = write_failure_analysis_artifacts(
        tmp_path, report, summary
    )
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["judged_relevant_product_count"] == 1
    lines = jsonl_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    summary_payload = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary_payload["query_count"] == 1
