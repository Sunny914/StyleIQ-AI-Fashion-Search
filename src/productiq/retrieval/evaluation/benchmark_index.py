"""Build a memory-bounded BM25 retriever for benchmark evaluation."""

from __future__ import annotations

from pathlib import Path

import pyarrow.parquet as pq  # type: ignore[import-untyped]  # type: ignore[import-untyped]

from productiq.retrieval.bm25_retriever import create_bm25_retriever
from productiq.retrieval.contracts import Retriever
from productiq.retrieval.evaluation.dataset import LexicalRetrievalBenchmark
from productiq.retrieval.lexical import LexicalIndexDocument, build_inverted_lexical_index


def _benchmark_query_terms(benchmark: LexicalRetrievalBenchmark) -> tuple[str, ...]:
    terms: set[str] = set()
    for query in benchmark.queries:
        for token in query.query_text.lower().split():
            stripped = token.strip()
            if stripped:
                terms.add(stripped)
    return tuple(sorted(terms))


def build_benchmark_scoped_bm25_retriever(
    representation_parquet_path: Path,
    benchmark: LexicalRetrievalBenchmark,
    *,
    max_docs_per_term: int = 500,
    max_total_docs: int = 8_000,
) -> tuple[Retriever, int]:
    """Construct a BM25 retriever over a benchmark-focused catalog slice.

    Includes all judged relevant product IDs plus up to ``max_docs_per_term`` products
    per benchmark query term (union). This is **not** identical to retrieval over the
    full ~367k catalog but yields reproducible BM25 metrics when the persisted index
    cannot be loaded (for example due to memory limits).
    """
    if max_docs_per_term <= 0:
        msg = "max_docs_per_term must be positive"
        raise ValueError(msg)
    if max_total_docs <= 0:
        msg = "max_total_docs must be positive"
        raise ValueError(msg)
    resolved = Path(representation_parquet_path)
    judged_ids: set[str] = set()
    for query in benchmark.queries:
        judged_ids.update(query.relevant_product_ids)
    terms = _benchmark_query_terms(benchmark)
    term_hits: dict[str, set[str]] = {term: set() for term in terms}
    selected_ids: set[str] = set(judged_ids)
    parquet_file = pq.ParquetFile(resolved)
    for batch in parquet_file.iter_batches(batch_size=10_000, columns=["product_id", "lexical_text"]):
        product_ids = batch.column("product_id").to_pylist()
        lexical_texts = batch.column("lexical_text").to_pylist()
        for product_id, lexical_text in zip(product_ids, lexical_texts, strict=True):
            pid = str(product_id).strip()
            text = str(lexical_text or "").lower()
            if pid in judged_ids:
                continue
            for term in terms:
                if len(selected_ids) >= max_total_docs:
                    break
                bucket = term_hits[term]
                if len(bucket) >= max_docs_per_term:
                    continue
                if term in text:
                    bucket.add(pid)
                    selected_ids.add(pid)
            if len(selected_ids) >= max_total_docs:
                break
        if len(selected_ids) >= max_total_docs:
            break
    remaining_ids = set(selected_ids)
    documents: list[LexicalIndexDocument] = []
    parquet_file = pq.ParquetFile(resolved)
    for batch in parquet_file.iter_batches(batch_size=10_000, columns=["product_id", "lexical_text"]):
        product_ids = batch.column("product_id").to_pylist()
        lexical_texts = batch.column("lexical_text").to_pylist()
        for product_id, lexical_text in zip(product_ids, lexical_texts, strict=True):
            pid = str(product_id).strip()
            if pid not in remaining_ids:
                continue
            documents.append(
                LexicalIndexDocument(product_id=pid, lexical_text=str(lexical_text or ""))
            )
            remaining_ids.discard(pid)
            if not remaining_ids:
                break
        if not remaining_ids:
            break
    index = build_inverted_lexical_index(documents)
    return create_bm25_retriever(index), len(documents)


__all__ = ["build_benchmark_scoped_bm25_retriever"]
