"""Tests for PgVectorProductVectorIndex adapter."""

from __future__ import annotations

from productiq.retrieval.pgvector_vector_index import (
    PgVectorProductVectorIndex,
    pgvector_vector_index_satisfies_protocol,
)
from productiq.retrieval.semantic import VectorIndex


def test_pgvector_adapter_satisfies_vector_index_protocol() -> None:
    class _Engine:
        pass

    index = PgVectorProductVectorIndex(engine=_Engine())  # type: ignore[arg-type]
    assert isinstance(index, VectorIndex)
    assert pgvector_vector_index_satisfies_protocol(index)
