"""Tests for Phase 4.6 BM25 lexical index construction."""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from productiq.exceptions.base import LexicalRetrievalError
from productiq.retrieval import BM25Scorer, build_inverted_lexical_index
from productiq.retrieval.bm25 import BM25Config
from productiq.retrieval.index_builder import (
    _move_aside_if_exists,
    _publish_index_artifacts,
    build_bm25_lexical_index_from_representation_dataset,
    build_inverted_lexical_index_from_lexical_rows,
    compute_lexical_index_statistics,
    load_bm25_lexical_index_manifest,
    load_inverted_lexical_index,
    save_inverted_lexical_index,
    validate_inverted_lexical_index_integrity,
)
from productiq.retrieval.index_schema import (
    BM25_LEXICAL_INDEX_FILENAME,
    BM25_LEXICAL_INDEX_SCHEMA_VERSION,
    INDEX_INPUT_LEXICAL_TEXT_COLUMN,
    INDEX_INPUT_PRODUCT_ID_COLUMN,
)
from productiq.retrieval.lexical import LexicalIndexDocument


def _write_representation_parquet(rows: list[dict[str, object]], path: Path) -> None:
    if rows:
        frame = pd.DataFrame(rows)
    else:
        frame = pd.DataFrame(
            columns=[INDEX_INPUT_PRODUCT_ID_COLUMN, INDEX_INPUT_LEXICAL_TEXT_COLUMN]
        )
    frame[INDEX_INPUT_PRODUCT_ID_COLUMN] = frame[INDEX_INPUT_PRODUCT_ID_COLUMN].astype("string")
    frame[INDEX_INPUT_LEXICAL_TEXT_COLUMN] = frame[INDEX_INPUT_LEXICAL_TEXT_COLUMN].astype("string")
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, index=False)


def test_missing_required_column_fails(tmp_path: Path) -> None:
    path = tmp_path / "bad.parquet"
    pd.DataFrame({"product_id": ["P1"]}).to_parquet(path, index=False)
    with pytest.raises(LexicalRetrievalError, match="missing required columns"):
        build_bm25_lexical_index_from_representation_dataset(path)


def test_duplicate_product_id_fails(tmp_path: Path) -> None:
    path = tmp_path / "dup.parquet"
    _write_representation_parquet(
        [
            {"product_id": "P1", "lexical_text": "nike"},
            {"product_id": "P1", "lexical_text": "adidas"},
        ],
        path,
    )
    with pytest.raises(LexicalRetrievalError, match="duplicate product_id"):
        build_bm25_lexical_index_from_representation_dataset(path)


def test_empty_product_id_fails(tmp_path: Path) -> None:
    path = tmp_path / "empty_id.parquet"
    _write_representation_parquet([{"product_id": "  ", "lexical_text": "nike"}], path)
    with pytest.raises(LexicalRetrievalError, match="product_id must not be empty"):
        build_bm25_lexical_index_from_representation_dataset(path)


def test_empty_corpus_builds_empty_index(tmp_path: Path) -> None:
    path = tmp_path / "empty.parquet"
    _write_representation_parquet([], path)
    result = build_bm25_lexical_index_from_representation_dataset(path)
    assert result.statistics.document_count == 0
    assert result.index_path.is_file()
    assert result.manifest_path.is_file()
    loaded = load_inverted_lexical_index(result.index_path)
    assert loaded.total_document_count() == 0


def test_empty_lexical_text_retained_with_zero_length(tmp_path: Path) -> None:
    path = tmp_path / "blank.parquet"
    _write_representation_parquet([{"product_id": "P1", "lexical_text": ""}], path)
    result = build_bm25_lexical_index_from_representation_dataset(path)
    assert result.statistics.document_count == 1
    assert result.statistics.empty_lexical_document_count == 1
    assert result.index.document_length("P1") == 0
    assert result.index.lookup_term("nike") == ()


def test_duplicate_lexical_text_distinct_products(tmp_path: Path) -> None:
    path = tmp_path / "same_text.parquet"
    _write_representation_parquet(
        [
            {"product_id": "P001", "lexical_text": "nike black shoes"},
            {"product_id": "P002", "lexical_text": "nike black shoes"},
        ],
        path,
    )
    result = build_bm25_lexical_index_from_representation_dataset(path)
    assert result.statistics.document_count == 2
    nike_postings = result.index.lookup_term("nike")
    assert {posting.product_id for posting in nike_postings} == {"P001", "P002"}


def test_deterministic_build_and_manifest(tmp_path: Path) -> None:
    rows = [
        {"product_id": "P2", "lexical_text": "black shoes"},
        {"product_id": "P1", "lexical_text": "nike shoes"},
    ]
    first_source = tmp_path / "first.parquet"
    second_source = tmp_path / "second.parquet"
    _write_representation_parquet(rows, first_source)
    _write_representation_parquet(rows, second_source)

    first = build_bm25_lexical_index_from_representation_dataset(
        first_source,
        index_path=tmp_path / "first.pkl",
        manifest_path=tmp_path / "first.manifest.json",
    )
    second = build_bm25_lexical_index_from_representation_dataset(
        second_source,
        index_path=tmp_path / "second.pkl",
        manifest_path=tmp_path / "second.manifest.json",
    )

    assert first.index == second.index
    assert first.index.document_ids == ("P1", "P2")
    first_manifest = json.loads(first.manifest_path.read_text())
    second_manifest = json.loads(second.manifest_path.read_text())
    for key in ("build_duration_seconds", "output_filename"):
        first_manifest.pop(key)
        second_manifest.pop(key)
    assert first_manifest == second_manifest


def test_index_statistics(tmp_path: Path) -> None:
    index = build_inverted_lexical_index(
        [
            LexicalIndexDocument(product_id="P1", lexical_text="nike nike shoes"),
            LexicalIndexDocument(product_id="P2", lexical_text=""),
        ]
    )
    stats = compute_lexical_index_statistics(index)
    assert stats.document_count == 2
    assert stats.total_document_length == 3
    assert stats.average_document_length == 1.5
    assert stats.unique_term_count == 2
    assert stats.total_posting_count == 2
    assert stats.empty_lexical_document_count == 1


def test_save_load_round_trip_and_bm25(tmp_path: Path) -> None:
    index = build_inverted_lexical_index(
        [
            LexicalIndexDocument(product_id="P1", lexical_text="nike black shoes"),
            LexicalIndexDocument(product_id="P2", lexical_text="adidas black shoes"),
        ]
    )
    artifact = tmp_path / "index.pkl"
    save_inverted_lexical_index(index, artifact)
    loaded = load_inverted_lexical_index(artifact)
    assert loaded.lookup_term("nike") == index.lookup_term("nike")
    scorer = BM25Scorer(loaded)
    assert scorer.score_lexical_query("black nike")


def test_manifest_fields(tmp_path: Path) -> None:
    path = tmp_path / "data.parquet"
    _write_representation_parquet([{"product_id": "P1", "lexical_text": "nike shoes"}], path)
    result = build_bm25_lexical_index_from_representation_dataset(path)
    manifest = load_bm25_lexical_index_manifest(result.manifest_path)
    assert manifest.schema_version == BM25_LEXICAL_INDEX_SCHEMA_VERSION
    assert manifest.bm25_k1 == BM25Config().k1
    assert manifest.document_count == 1
    assert manifest.output_filename == BM25_LEXICAL_INDEX_FILENAME


def test_publish_restores_index_when_manifest_replace_fails(tmp_path: Path) -> None:
    final_index = tmp_path / "index.pkl"
    final_manifest = tmp_path / "manifest.json"
    final_index.write_bytes(b"original-index")
    final_manifest.write_text('{"existing": true}\n', encoding="utf-8")

    temp_index = tmp_path / "temp_index.pkl"
    temp_manifest = tmp_path / "temp_manifest.json"
    temp_index.write_bytes(b"new-index")
    temp_manifest.write_text('{"new": true}\n', encoding="utf-8")

    original_move = _move_aside_if_exists
    move_calls = 0

    def flaky_move_aside(path: Path) -> Path | None:
        nonlocal move_calls
        move_calls += 1
        if move_calls == 2:
            raise OSError("manifest backup failed")
        return original_move(path)

    with (
        patch(
            "productiq.retrieval.index_builder._move_aside_if_exists",
            side_effect=flaky_move_aside,
        ),
        pytest.raises(OSError),
    ):
        _publish_index_artifacts(
            temp_index_path=temp_index,
            temp_manifest_path=temp_manifest,
            final_index_path=final_index,
            final_manifest_path=final_manifest,
        )

    assert final_index.read_bytes() == b"original-index"
    assert final_manifest.read_text(encoding="utf-8") == '{"existing": true}\n'


def test_build_from_rows_matches_document_builder() -> None:
    rows = [("P1", "nike shoes"), ("P2", "")]
    from_rows = build_inverted_lexical_index_from_lexical_rows(rows)
    from_docs = build_inverted_lexical_index(
        [
            LexicalIndexDocument(product_id="P1", lexical_text="nike shoes"),
            LexicalIndexDocument(product_id="P2", lexical_text=""),
        ]
    )
    assert from_rows == from_docs
    validate_inverted_lexical_index_integrity(from_rows)


@pytest.mark.skipif(
    os.environ.get("PRODUCTIQ_BUILD_FULL_INDEX") != "1",
    reason="Set PRODUCTIQ_BUILD_FULL_INDEX=1 to build the full catalog index",
)
def test_build_full_representation_index(tmp_path: Path) -> None:
    source = Path("resources/processed/product_representations.parquet")
    if not source.is_file():
        pytest.skip("representation dataset artifact not present")
    output_index = tmp_path / "full_index.pkl"
    output_manifest = tmp_path / "full_index.manifest.json"
    result = build_bm25_lexical_index_from_representation_dataset(
        source,
        index_path=output_index,
        manifest_path=output_manifest,
    )
    loaded = load_inverted_lexical_index(output_index)
    assert result.statistics.document_count == 367172
    assert loaded.total_document_count() == result.statistics.document_count


@pytest.mark.skipif(
    os.environ.get("PRODUCTIQ_PUBLISH_FULL_INDEX") != "1",
    reason="Set PRODUCTIQ_PUBLISH_FULL_INDEX=1 to publish the full index artifact",
)
def test_publish_full_index_to_processed_directory() -> None:
    source = Path("resources/processed/product_representations.parquet")
    if not source.is_file():
        pytest.skip("representation dataset artifact not present")
    result = build_bm25_lexical_index_from_representation_dataset(source)
    assert result.index_path.is_file()
    assert result.manifest_path.is_file()
    loaded = load_inverted_lexical_index(result.index_path)
    manifest = load_bm25_lexical_index_manifest(result.manifest_path)
    assert loaded.total_document_count() == manifest.document_count == 367172
    assert manifest.source_representation_checksum == (
        "7fc2b6c08ef03233bdae1c845f4a087cd578fdb6d861b7d64ec72c71e92c3379"
    )
