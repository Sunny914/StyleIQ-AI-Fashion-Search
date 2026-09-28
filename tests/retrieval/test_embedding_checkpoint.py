"""Checkpoint/resume and device tests for Phase 4.11."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from productiq.exceptions.base import SemanticRetrievalError
from productiq.retrieval.embedding_builder import (
    generate_product_embeddings_from_representation_dataset,
    validate_embedding_product_ids_match_representation,
    validate_embeddings_parquet_integrity,
)
from productiq.retrieval.embedding_checkpoint import (
    build_run_configuration,
    checkpoint_path,
    load_checkpoint,
    new_checkpoint,
    save_checkpoint,
)
from productiq.retrieval.embedding_device import get_torch_runtime_info, resolve_embedding_device
from productiq.retrieval.embedding_schema import (
    EMBEDDING_INPUT_PRODUCT_ID_COLUMN,
    EMBEDDING_INPUT_SEMANTIC_TEXT_COLUMN,
    PRODUCT_EMBEDDINGS_FILENAME,
)
from tests.retrieval.test_embedding_generation import (
    FakeDocumentEncoder,
    _write_mini_representation_parquet,
)


def test_resolve_device_auto_and_cpu() -> None:
    cpu = resolve_embedding_device("cpu")
    assert cpu.selected == "cpu"
    auto = resolve_embedding_device("auto")
    assert auto.selected in {"cpu", "cuda"}


def test_cuda_requested_without_fallback_raises_when_unavailable() -> None:
    runtime = get_torch_runtime_info()
    if runtime.cuda_available:
        pytest.skip("CUDA is available on this host")
    with pytest.raises(SemanticRetrievalError, match="CUDA was requested"):
        resolve_embedding_device("cuda", allow_cpu_fallback=False)


def test_incompatible_checkpoint_rejected(tmp_path: Path) -> None:
    source = tmp_path / "product_representations.parquet"
    rows = [
        {EMBEDDING_INPUT_PRODUCT_ID_COLUMN: f"p{i}", EMBEDDING_INPUT_SEMANTIC_TEXT_COLUMN: f"text {i}"}
        for i in range(5)
    ]
    _write_mini_representation_parquet(source, rows)
    manifest = {"checksum": "abc123", "row_count": 5}
    (tmp_path / "product_representations.manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    config = build_run_configuration(
        source_manifest=manifest,
        target_product_count=5,
        model_id="BAAI/bge-small-en-v1.5",
        model_revision="rev1",
        embedding_dimension=384,
        batch_size=2,
        device="cpu",
        chunk_size=2,
    )
    ckpt_dir = tmp_path / ".embedding_generation"
    ckpt_dir.mkdir()
    save_checkpoint(
        checkpoint_path(ckpt_dir),
        new_checkpoint(config, completed_product_count=2, chunk_file_count=1),
    )
    with pytest.raises(SemanticRetrievalError, match="in-progress checkpoint data exists"):
        generate_product_embeddings_from_representation_dataset(
            source,
            encoder=FakeDocumentEncoder(),
            max_products=5,
            use_checkpoint=True,
            fresh_run=False,
            publish=False,
            checkpoint_dir=ckpt_dir,
        )


def test_checkpoint_resume_completes_remaining_products(tmp_path: Path) -> None:
    source = tmp_path / "product_representations.parquet"
    rows = [
        {EMBEDDING_INPUT_PRODUCT_ID_COLUMN: f"p{i:02d}", EMBEDDING_INPUT_SEMANTIC_TEXT_COLUMN: f"text {i}"}
        for i in range(30)
    ]
    _write_mini_representation_parquet(source, rows)
    manifest = {"checksum": "deadbeef", "row_count": 30}
    (tmp_path / "product_representations.manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    ckpt_dir = tmp_path / ".embedding_generation"
    encoder = FakeDocumentEncoder()
    partial_out = tmp_path / "partial.parquet"
    first = generate_product_embeddings_from_representation_dataset(
        source,
        embeddings_path=partial_out,
        encoder=encoder,
        max_products=20,
        use_checkpoint=True,
        fresh_run=True,
        publish=False,
        checkpoint_dir=ckpt_dir,
        batch_size=5,
        chunk_size=10,
    )
    assert first.product_count == 20
    save_checkpoint(
        checkpoint_path(ckpt_dir),
        new_checkpoint(
            build_run_configuration(
                source_manifest=manifest,
                target_product_count=30,
                model_id=encoder.model_id,
                model_revision=encoder.model_revision,
                embedding_dimension=384,
                batch_size=5,
                device=encoder.device,
                chunk_size=10,
            ),
            completed_product_count=20,
            last_product_id="p19",
            chunk_file_count=2,
            status="in_progress",
        ),
    )
    out = tmp_path / PRODUCT_EMBEDDINGS_FILENAME
    result = generate_product_embeddings_from_representation_dataset(
        source,
        embeddings_path=out,
        encoder=encoder,
        max_products=30,
        use_checkpoint=True,
        resume=True,
        publish=False,
        checkpoint_dir=ckpt_dir,
        batch_size=5,
        chunk_size=10,
    )
    assert result.product_count == 30
    validate_embeddings_parquet_integrity(out, expected_row_count=30, expected_dimension=384)
    validate_embedding_product_ids_match_representation(out, source)
    completed = load_checkpoint(checkpoint_path(ckpt_dir))
    assert completed.status == "complete"
    assert completed.completed_product_count == 30
