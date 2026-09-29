"""Read-only attribute vocabulary profiling for canonical product data."""

from __future__ import annotations

from dataclasses import dataclass
from functools import partial

import pandas as pd

from data.attributes.rules import (
    ATTRIBUTE_VOCABULARY_RULES,
    expression_matches,
    normalize_attribute_text,
)
from data.attributes.schema import ATTRIBUTE_TEXT_COLUMN, REQUIRED_CANONICAL_COLUMNS
from productiq.exceptions import DataAttributeError


@dataclass(frozen=True)
class VocabularyTermSummary:
    """Coverage summary for one controlled vocabulary expression."""

    attribute: str
    canonical_value: str
    expression: str
    row_count: int
    coverage_pct: float


@dataclass(frozen=True)
class AttributeVocabularyProfile:
    """Read-only vocabulary coverage profile for canonical descriptions."""

    total_rows: int
    term_summaries: tuple[VocabularyTermSummary, ...]

    def summaries_for_attribute(self, attribute: str) -> tuple[VocabularyTermSummary, ...]:
        """Return term summaries for one attribute."""
        return tuple(summary for summary in self.term_summaries if summary.attribute == attribute)


class ProductAttributeVocabularyProfiler:
    """Profile controlled vocabulary coverage without modifying input data."""

    def profile(self, dataframe: pd.DataFrame) -> AttributeVocabularyProfile:
        """Profile vocabulary coverage for canonical product descriptions."""
        if not isinstance(dataframe, pd.DataFrame):
            msg = "Attribute profiling input must be a pandas DataFrame"
            raise DataAttributeError(msg)

        missing_columns = [
            column for column in REQUIRED_CANONICAL_COLUMNS if column not in dataframe.columns
        ]
        if missing_columns:
            msg = f"Missing required canonical columns for attribute profiling: {', '.join(missing_columns)}"
            raise DataAttributeError(msg)

        if ATTRIBUTE_TEXT_COLUMN not in dataframe.columns:
            msg = f"Missing required attribute text column: {ATTRIBUTE_TEXT_COLUMN}"
            raise DataAttributeError(msg)

        total_rows = len(dataframe)
        normalized_descriptions = dataframe[ATTRIBUTE_TEXT_COLUMN].map(normalize_attribute_text)
        summaries: list[VocabularyTermSummary] = []

        for rule in ATTRIBUTE_VOCABULARY_RULES:
            for expression in rule.expressions:
                matches_expression = partial(expression_matches, expression=expression)
                row_count = int(normalized_descriptions.map(matches_expression).sum())
                coverage_pct = (row_count / total_rows * 100.0) if total_rows else 0.0
                summaries.append(
                    VocabularyTermSummary(
                        attribute=rule.attribute,
                        canonical_value=rule.canonical_value,
                        expression=expression,
                        row_count=row_count,
                        coverage_pct=coverage_pct,
                    )
                )

        return AttributeVocabularyProfile(
            total_rows=total_rows,
            term_summaries=tuple(summaries),
        )
