"""Lexical retrieval foundations: tokenization and inverted index (Phase 4.4)."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from productiq.exceptions.base import LexicalRetrievalError
from productiq.retrieval.query_for_retrieval import RetrievalQueryView

# Conservative token pattern: contiguous alphanumeric sequences (no stemming/synonyms).
_LEXICAL_TOKEN_PATTERN = re.compile(r"[a-z0-9]+", re.IGNORECASE)


def normalize_lexical_surface_text(text: str) -> str:
    """Collapse surrounding and internal whitespace (aligned with Phase 3 lexical whitespace rules)."""
    return re.sub(r"\s+", " ", text.strip())


def tokenize_lexical_text(text: str | None) -> tuple[str, ...]:
    """Tokenize lexical text into deterministic lowercase terms."""
    if text is None:
        return ()
    surface = normalize_lexical_surface_text(text)
    if not surface:
        return ()
    return tuple(_LEXICAL_TOKEN_PATTERN.findall(surface.casefold()))


def normalize_lexical_query_term(term: str) -> str:
    """Normalize a single lookup term for index access."""
    normalized = term.strip().casefold()
    if not normalized:
        msg = "lexical term must not be empty"
        raise LexicalRetrievalError(msg)
    return normalized


class LexicalPosting(BaseModel):
    """One document's posting for a single index term."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    product_id: str = Field(min_length=1)
    term_frequency: int = Field(gt=0)

    @field_validator("product_id")
    @classmethod
    def validate_product_id(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            msg = "product_id must not be empty"
            raise ValueError(msg)
        return stripped


class LexicalIndexDocument(BaseModel):
    """Product document keyed by ``product_id`` with searchable ``lexical_text``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    product_id: str = Field(min_length=1)
    lexical_text: str = ""

    @field_validator("product_id")
    @classmethod
    def validate_product_id(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            msg = "product_id must not be empty"
            raise ValueError(msg)
        return stripped


class InvertedLexicalIndex(BaseModel):
    """Deterministic inverted index with TF/DF/length statistics (no relevance scoring)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    postings_by_term: dict[str, tuple[LexicalPosting, ...]]
    document_lengths: dict[str, int]
    document_ids: tuple[str, ...]

    def total_document_count(self) -> int:
        return len(self.document_ids)

    def document_length(self, product_id: str) -> int:
        if product_id not in self.document_lengths:
            msg = f"unknown product_id for document length: {product_id}"
            raise LexicalRetrievalError(msg)
        return self.document_lengths[product_id]

    def lookup_term(self, term: str) -> tuple[LexicalPosting, ...]:
        normalized = normalize_lexical_query_term(term)
        return self.postings_by_term.get(normalized, ())

    def lookup_terms(self, terms: Sequence[str]) -> dict[str, tuple[LexicalPosting, ...]]:
        return {normalize_lexical_query_term(term): self.lookup_term(term) for term in terms}

    def document_frequency(self, term: str) -> int:
        return len(self.lookup_term(term))

    def term_frequency(self, term: str, product_id: str) -> int:
        for posting in self.lookup_term(term):
            if posting.product_id == product_id:
                return posting.term_frequency
        return 0

    def retrieve_candidate_product_ids(self, query_lexical_text: str) -> tuple[str, ...]:
        """Return product IDs matching any query term (union), sorted ascending for stability."""
        query_terms = tokenize_lexical_text(query_lexical_text)
        if not query_terms:
            return ()
        candidates: set[str] = set()
        for term in query_terms:
            for posting in self.lookup_term(term):
                candidates.add(posting.product_id)
        return tuple(sorted(candidates))


def assemble_inverted_lexical_index(
    document_ids: Sequence[str],
    document_lengths: Mapping[str, int],
    term_to_postings: Mapping[str, Mapping[str, int]],
) -> InvertedLexicalIndex:
    """Assemble a frozen inverted index from deterministic build parts (Phase 4.4/4.6)."""
    postings_by_term: dict[str, tuple[LexicalPosting, ...]] = {}
    for term in sorted(term_to_postings):
        postings_map = term_to_postings[term]
        postings = tuple(
            LexicalPosting(product_id=product_id, term_frequency=postings_map[product_id])
            for product_id in sorted(postings_map)
        )
        postings_by_term[term] = postings

    return InvertedLexicalIndex(
        postings_by_term=postings_by_term,
        document_lengths=dict(document_lengths),
        document_ids=tuple(document_ids),
    )


def build_inverted_lexical_index(documents: Sequence[LexicalIndexDocument]) -> InvertedLexicalIndex:
    """Build an inverted index from product lexical documents."""
    if not documents:
        return InvertedLexicalIndex(
            postings_by_term={},
            document_lengths={},
            document_ids=(),
        )

    seen_ids: set[str] = set()
    document_lengths: dict[str, int] = {}
    document_ids: list[str] = []
    term_to_postings: dict[str, dict[str, int]] = {}

    for document in documents:
        product_id = document.product_id
        if product_id in seen_ids:
            msg = f"duplicate product_id in lexical index build: {product_id}"
            raise LexicalRetrievalError(msg)
        seen_ids.add(product_id)
        document_ids.append(product_id)

        tokens = tokenize_lexical_text(document.lexical_text)
        document_lengths[product_id] = len(tokens)

        term_counts: dict[str, int] = {}
        for token in tokens:
            term_counts[token] = term_counts.get(token, 0) + 1

        for term, tf in term_counts.items():
            postings_for_term = term_to_postings.setdefault(term, {})
            postings_for_term[product_id] = tf

    return assemble_inverted_lexical_index(document_ids, document_lengths, term_to_postings)


def build_inverted_lexical_index_from_mapping(
    documents: Mapping[str, str],
) -> InvertedLexicalIndex:
    """Build an index from ``product_id`` → ``lexical_text`` mappings."""
    ordered_ids = sorted(documents)
    built_documents = [
        LexicalIndexDocument(product_id=product_id, lexical_text=documents[product_id])
        for product_id in ordered_ids
    ]
    return build_inverted_lexical_index(built_documents)


def retrieve_lexical_candidates(
    index: InvertedLexicalIndex,
    query_lexical_text: str,
) -> tuple[str, ...]:
    """Candidate retrieval from raw lexical query text (no ranking)."""
    return index.retrieve_candidate_product_ids(query_lexical_text)


def retrieve_lexical_candidates_from_view(
    index: InvertedLexicalIndex,
    view: RetrievalQueryView,
) -> tuple[str, ...]:
    """Candidate retrieval from Phase 4.3 ``RetrievalQueryView``."""
    return index.retrieve_candidate_product_ids(view.lexical_retrieval_text)


def inverted_lexical_index_to_dict(index: InvertedLexicalIndex) -> dict[str, Any]:
    """Serialize index statistics for notebooks and debugging."""
    return index.model_dump(mode="json")


__all__ = [
    "InvertedLexicalIndex",
    "LexicalIndexDocument",
    "LexicalPosting",
    "assemble_inverted_lexical_index",
    "build_inverted_lexical_index",
    "build_inverted_lexical_index_from_mapping",
    "inverted_lexical_index_to_dict",
    "normalize_lexical_query_term",
    "normalize_lexical_surface_text",
    "retrieve_lexical_candidates",
    "retrieve_lexical_candidates_from_view",
    "tokenize_lexical_text",
]
