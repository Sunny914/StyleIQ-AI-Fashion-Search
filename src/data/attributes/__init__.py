"""Product attribute engineering utilities."""

from __future__ import annotations

import importlib
from typing import Any

__all__ = [
    "ATTRIBUTE_COLUMN_ORDER",
    "ATTRIBUTE_DEFINITIONS",
    "ATTRIBUTE_VOCABULARY_RULES",
    "MULTI_VALUE_DELIMITER",
    "AttributeExtractionReport",
    "AttributeExtractionResult",
    "AttributeVocabularyProfile",
    "ProductAttributeExtractor",
    "ProductAttributeVocabularyProfiler",
    "VocabularyRule",
    "VocabularyTermSummary",
    "expression_matches",
    "extract_attribute_value",
    "normalize_attribute_text",
]


def _lazy(module: str, *names: str) -> dict[str, tuple[str, str]]:
    return {name: (module, name) for name in names}


_LAZY_EXPORTS: dict[str, tuple[str, str]] = {}
_LAZY_EXPORTS.update(
    _lazy(
        "data.attributes.schema",
        "ATTRIBUTE_COLUMN_ORDER",
        "ATTRIBUTE_DEFINITIONS",
        "MULTI_VALUE_DELIMITER",
    )
)
_LAZY_EXPORTS.update(
    _lazy(
        "data.attributes.extractor",
        "AttributeExtractionReport",
        "AttributeExtractionResult",
        "ProductAttributeExtractor",
    )
)
_LAZY_EXPORTS.update(
    _lazy(
        "data.attributes.profiler",
        "AttributeVocabularyProfile",
        "ProductAttributeVocabularyProfiler",
        "VocabularyTermSummary",
    )
)
_LAZY_EXPORTS.update(
    _lazy(
        "data.attributes.rules",
        "ATTRIBUTE_VOCABULARY_RULES",
        "VocabularyRule",
        "expression_matches",
        "extract_attribute_value",
        "normalize_attribute_text",
    )
)


def __getattr__(name: str) -> Any:
    if name not in _LAZY_EXPORTS:
        msg = f"module {__name__!r} has no attribute {name!r}"
        raise AttributeError(msg)
    module_name, attr_name = _LAZY_EXPORTS[name]
    module = importlib.import_module(module_name)
    return getattr(module, attr_name)


def __dir__() -> list[str]:
    return sorted(__all__)
