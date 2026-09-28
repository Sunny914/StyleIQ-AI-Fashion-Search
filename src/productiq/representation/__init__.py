"""Structured product representation (Phase 3.3).

Public symbols are loaded lazily so retrieval/embedding modules can import
``query_contract`` (and similar) without pulling in the Phase 3.11 dataset writer
and Phase 1 ``data.export`` stack at package import time.
"""

from __future__ import annotations

import importlib
from typing import Any

__all__ = [
    "CatalogRepresentationQualityReport",
    "FilteringRepresentation",
    "FilteringRepresentationBuilder",
    "LexicalRepresentationBuilder",
    "ProductRepresentation",
    "ProductRepresentationBundle",
    "ProductRepresentationPipeline",
    "ProductTextBuilder",
    "QueryFilterConstraints",
    "QueryRepresentation",
    "QueryRepresentationBuilder",
    "RepresentationDatasetGenerator",
    "RepresentationQualityReport",
    "SemanticRepresentationBuilder",
    "build_filtering_representation",
    "build_filtering_representation_from_canonical",
    "build_lexical_text",
    "build_lexical_text_from_canonical",
    "build_product_representation",
    "build_product_representation_bundle",
    "build_product_representations",
    "build_product_text",
    "build_query_representation",
    "build_semantic_text",
    "build_semantic_text_from_canonical",
    "build_structured_lexical_text",
    "filtering_representation_to_dict",
    "generate_representation_dataset",
    "load_representation_dataset_manifest",
    "normalize_query_text",
    "parse_pipe_delimited_multivalue",
    "product_representation_bundle_to_dict",
    "query_representation_to_dict",
    "representation_to_dict",
    "representation_to_json",
    "summarize_representation_quality_reports",
    "validate_canonical_record_representation_quality",
    "validate_canonical_records_representation_quality",
    "validate_product_representation",
    "validate_product_representation_bundle",
    "validate_representation_dataset",
]


def _lazy(module: str, *names: str) -> dict[str, tuple[str, str]]:
    return {name: (module, name) for name in names}


_LAZY_EXPORTS: dict[str, tuple[str, str]] = {}
_LAZY_EXPORTS.update(
    _lazy(
        "productiq.representation.builder",
        "build_product_representation",
        "build_product_representations",
    )
)
_LAZY_EXPORTS.update(
    _lazy(
        "productiq.representation.dataset",
        "RepresentationDatasetGenerator",
        "generate_representation_dataset",
        "load_representation_dataset_manifest",
        "validate_representation_dataset",
    )
)
_LAZY_EXPORTS.update(
    _lazy(
        "productiq.representation.filtering",
        "FilteringRepresentation",
        "FilteringRepresentationBuilder",
        "build_filtering_representation",
        "build_filtering_representation_from_canonical",
        "filtering_representation_to_dict",
    )
)
_LAZY_EXPORTS.update(
    _lazy(
        "productiq.representation.lexical",
        "LexicalRepresentationBuilder",
        "build_lexical_text",
        "build_lexical_text_from_canonical",
        "build_structured_lexical_text",
    )
)
_LAZY_EXPORTS.update(
    _lazy(
        "productiq.representation.pipeline",
        "ProductRepresentationBundle",
        "ProductRepresentationPipeline",
        "build_product_representation_bundle",
        "product_representation_bundle_to_dict",
    )
)
_LAZY_EXPORTS.update(
    _lazy(
        "productiq.representation.quality",
        "CatalogRepresentationQualityReport",
        "RepresentationQualityReport",
        "summarize_representation_quality_reports",
        "validate_canonical_record_representation_quality",
        "validate_canonical_records_representation_quality",
        "validate_product_representation_bundle",
    )
)
_LAZY_EXPORTS.update(
    _lazy(
        "productiq.representation.query_contract",
        "QueryFilterConstraints",
        "QueryRepresentation",
        "QueryRepresentationBuilder",
        "build_query_representation",
        "normalize_query_text",
        "query_representation_to_dict",
    )
)
_LAZY_EXPORTS.update(_lazy("productiq.representation.schema", "ProductRepresentation"))
_LAZY_EXPORTS.update(
    _lazy(
        "productiq.representation.semantic",
        "SemanticRepresentationBuilder",
        "build_semantic_text",
        "build_semantic_text_from_canonical",
    )
)
_LAZY_EXPORTS.update(
    _lazy(
        "productiq.representation.serializers",
        "representation_to_dict",
        "representation_to_json",
    )
)
_LAZY_EXPORTS.update(_lazy("productiq.representation.text", "ProductTextBuilder", "build_product_text"))
_LAZY_EXPORTS.update(
    _lazy(
        "productiq.representation.validators",
        "parse_pipe_delimited_multivalue",
        "validate_product_representation",
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
