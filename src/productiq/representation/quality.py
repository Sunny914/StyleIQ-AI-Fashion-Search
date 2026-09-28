"""Representation quality validation for Phase 3.9 bundles (Phase 3.10)."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from productiq.exceptions.base import RepresentationQualityError
from productiq.representation.filtering import FilteringRepresentation
from productiq.representation.lexical import (
    build_lexical_text_from_canonical,
    normalize_lexical_description,
)
from productiq.representation.ontology import MULTI_VALUE_REPRESENTATION_FIELDS
from productiq.representation.pipeline import (
    ProductRepresentationBundle,
    build_product_representation_bundle,
)
from productiq.representation.schema import ProductRepresentation
from productiq.representation.semantic import build_semantic_text_from_canonical
from productiq.representation.text import (
    build_product_text,
    render_machine_token,
    render_multivalue,
    render_scalar_value,
)
from productiq.representation.validators import is_missing_value

QualityIssueCategory = Literal[
    "structural",
    "consistency",
    "degeneracy",
    "preservation",
    "description",
    "price",
    "color",
]

_STRUCTURED_MULTI_VALUE_FIELDS: tuple[str, ...] = tuple(sorted(MULTI_VALUE_REPRESENTATION_FIELDS))

_SCALAR_FACET_FIELDS: tuple[str, ...] = (
    "brand",
    "brand_normalized",
    "category_gender",
    "product_type",
)

_FIELD_COVERAGE_KEYS: tuple[str, ...] = (
    "brand",
    "category_gender",
    "product_type",
    "color",
    "pattern",
    "material",
    "fit",
    "sleeve",
    "neckline",
    "product_features",
    "style_attributes",
    "description",
)

_REPRESENTATION_COVERAGE_KEYS: tuple[str, ...] = ("text", "lexical", "semantic", "filtering")


class RepresentationQualityIssue(BaseModel):
    """Single representation quality finding (not retrieval relevance)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    category: QualityIssueCategory
    code: str
    message: str
    field: str | None = None


class RepresentationQualityReport(BaseModel):
    """Quality outcome for one ``ProductRepresentationBundle``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    valid: bool
    issues: tuple[RepresentationQualityIssue, ...]
    structural_issue_count: int = 0
    consistency_issue_count: int = 0
    degeneracy_issue_count: int = 0
    preservation_issue_count: int = 0
    description_issue_count: int = 0
    price_issue_count: int = 0
    color_issue_count: int = 0

    @property
    def issue_count(self) -> int:
        return len(self.issues)


class CatalogRepresentationQualityReport(BaseModel):
    """Aggregated observational metrics across many records (coverage is not accuracy)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    total_records: int
    valid_records: int
    invalid_records: int
    field_coverage: dict[str, float]
    representation_coverage: dict[str, float]
    degeneracy_issue_count: int
    consistency_issue_count: int
    total_issue_count: int


def _issue(
    category: QualityIssueCategory,
    code: str,
    message: str,
    *,
    field: str | None = None,
) -> RepresentationQualityIssue:
    return RepresentationQualityIssue(
        category=category,
        code=code,
        message=message,
        field=field,
    )


def _count_by_category(
    issues: tuple[RepresentationQualityIssue, ...],
) -> dict[QualityIssueCategory, int]:
    counts: dict[QualityIssueCategory, int] = {
        "structural": 0,
        "consistency": 0,
        "degeneracy": 0,
        "preservation": 0,
        "description": 0,
        "price": 0,
        "color": 0,
    }
    for item in issues:
        counts[item.category] += 1
    return counts


def _report_from_issues(issues: list[RepresentationQualityIssue]) -> RepresentationQualityReport:
    frozen = tuple(issues)
    counts = _count_by_category(frozen)
    return RepresentationQualityReport(
        valid=len(frozen) == 0,
        issues=frozen,
        structural_issue_count=counts["structural"],
        consistency_issue_count=counts["consistency"],
        degeneracy_issue_count=counts["degeneracy"],
        preservation_issue_count=counts["preservation"],
        description_issue_count=counts["description"],
        price_issue_count=counts["price"],
        color_issue_count=counts["color"],
    )


def _is_degenerate_text(value: str) -> bool:
    return value.strip() == ""


def _duplicate_labeled_clauses(text: str) -> list[str]:
    stripped = text.strip()
    if not stripped:
        return []
    body = stripped.removesuffix(".")
    labels: list[str] = []
    for clause in body.split(". "):
        clause = clause.strip()
        if ": " not in clause:
            continue
        labels.append(clause.split(": ", 1)[0])
    return labels


def _text_contains_rendered_scalar(text: str, raw: str) -> bool:
    rendered = render_scalar_value(raw)
    if not rendered:
        return False
    return rendered.casefold() in text.casefold()


def _text_contains_rendered_multivalue(text: str, values: list[str]) -> bool:
    for token in values:
        rendered = render_machine_token(token)
        if rendered and rendered.casefold() not in text.casefold():
            return False
    return True


def _check_degeneracy(bundle: ProductRepresentationBundle) -> list[RepresentationQualityIssue]:
    issues: list[RepresentationQualityIssue] = []
    for field_name, value in (
        ("text", bundle.text),
        ("lexical", bundle.lexical),
        ("semantic", bundle.semantic),
    ):
        if _is_degenerate_text(value):
            issues.append(
                _issue(
                    "degeneracy",
                    "empty_representation_text",
                    f"{field_name} must not be empty or whitespace-only",
                    field=field_name,
                )
            )
        if "None" in value and ": None" in value:
            issues.append(
                _issue(
                    "degeneracy",
                    "literal_none_in_text",
                    f"{field_name} contains a literal None label value",
                    field=field_name,
                )
            )
        labels = _duplicate_labeled_clauses(value)
        if len(labels) != len(set(labels)):
            issues.append(
                _issue(
                    "degeneracy",
                    "duplicate_field_labels",
                    f"{field_name} repeats labeled clauses",
                    field=field_name,
                )
            )
    return issues


def _check_product_filtering_consistency(
    product: ProductRepresentation,
    filtering: FilteringRepresentation,
) -> list[RepresentationQualityIssue]:
    issues: list[RepresentationQualityIssue] = []
    if product.product_id != filtering.product_id:
        issues.append(
            _issue(
                "consistency",
                "product_id_mismatch",
                "filtering.product_id must match product.product_id",
                field="product_id",
            )
        )
    for field_name in _SCALAR_FACET_FIELDS:
        if getattr(product, field_name) != getattr(filtering, field_name):
            issues.append(
                _issue(
                    "consistency",
                    "scalar_facet_mismatch",
                    f"filtering.{field_name} must match product.{field_name}",
                    field=field_name,
                )
            )
    for field_name in _STRUCTURED_MULTI_VALUE_FIELDS:
        if getattr(product, field_name) != getattr(filtering, field_name):
            issues.append(
                _issue(
                    "consistency",
                    "multivalue_facet_mismatch",
                    f"filtering.{field_name} must match product.{field_name}",
                    field=field_name,
                )
            )
    return issues


def _check_preservation(bundle: ProductRepresentationBundle) -> list[RepresentationQualityIssue]:
    product = bundle.product
    issues: list[RepresentationQualityIssue] = []
    brand_raw = product.brand if product.brand is not None else product.brand_normalized
    if brand_raw is not None:
        for field_name, text in (
            ("text", bundle.text),
            ("lexical", bundle.lexical),
            ("semantic", bundle.semantic),
        ):
            if not _text_contains_rendered_scalar(text, brand_raw):
                issues.append(
                    _issue(
                        "preservation",
                        "brand_not_preserved",
                        f"brand must appear in {field_name} when populated on product",
                        field=field_name,
                    )
                )
    if not _text_contains_rendered_scalar(bundle.text, product.category_gender):
        issues.append(
            _issue(
                "preservation",
                "category_not_preserved",
                "category_gender must appear in product text",
                field="text",
            )
        )
    for field_name, text in (("lexical", bundle.lexical), ("semantic", bundle.semantic)):
        if not _text_contains_rendered_scalar(text, product.category_gender):
            issues.append(
                _issue(
                    "preservation",
                    "category_not_preserved",
                    f"category_gender must appear in {field_name}",
                    field=field_name,
                )
            )
    if product.product_type is not None:
        for field_name, text in (
            ("text", bundle.text),
            ("lexical", bundle.lexical),
            ("semantic", bundle.semantic),
        ):
            if not _text_contains_rendered_scalar(text, product.product_type):
                issues.append(
                    _issue(
                        "preservation",
                        "product_type_not_preserved",
                        f"product_type must appear in {field_name} when populated",
                        field=field_name,
                    )
                )
    if product.color is not None:
        rendered = render_multivalue(product.color)
        if rendered and rendered.casefold() not in bundle.text.casefold():
            issues.append(
                _issue(
                    "preservation",
                    "color_not_preserved",
                    "normalized color must appear in product text when populated",
                    field="color",
                )
            )
        for field_name, text in (("lexical", bundle.lexical), ("semantic", bundle.semantic)):
            if not _text_contains_rendered_multivalue(text, product.color):
                issues.append(
                    _issue(
                        "preservation",
                        "color_not_preserved",
                        f"normalized color must appear in {field_name} when populated",
                        field=field_name,
                    )
                )
        if product.color != bundle.filtering.color:
            issues.append(
                _issue(
                    "color",
                    "normalized_color_filtering_mismatch",
                    "filtering.color must match product.color when populated",
                    field="color",
                )
            )
    for field_name in _STRUCTURED_MULTI_VALUE_FIELDS:
        values = getattr(product, field_name)
        if values is None:
            continue
        if not _text_contains_rendered_multivalue(bundle.text, values) and field_name != "color":
            rendered = render_multivalue(values)
            if rendered and rendered.casefold() not in bundle.text.casefold():
                issues.append(
                    _issue(
                        "preservation",
                        "multivalue_not_preserved",
                        f"product.{field_name} must appear in product text when populated",
                        field=field_name,
                    )
                )
        for text_field, text in (("lexical", bundle.lexical), ("semantic", bundle.semantic)):
            if not _text_contains_rendered_multivalue(text, values):
                issues.append(
                    _issue(
                        "preservation",
                        "multivalue_not_preserved",
                        f"product.{field_name} must appear in {text_field} when populated",
                        field=field_name,
                    )
                )
    return issues


def _check_description(
    bundle: ProductRepresentationBundle,
    record: Mapping[str, Any],
) -> list[RepresentationQualityIssue]:
    normalized = normalize_lexical_description(record.get("description"))
    if normalized is None:
        return []
    issues: list[RepresentationQualityIssue] = []
    if normalized not in bundle.lexical:
        issues.append(
            _issue(
                "description",
                "description_missing_lexical",
                "normalized description must appear in lexical text when canonical description is present",
                field="lexical",
            )
        )
    expected_semantic = f"Description: {normalized}"
    if expected_semantic not in bundle.semantic:
        issues.append(
            _issue(
                "description",
                "description_missing_semantic",
                "normalized description must appear in semantic text when canonical description is present",
                field="semantic",
            )
        )
    return issues


def _check_prices_and_color_metadata(
    bundle: ProductRepresentationBundle,
    record: Mapping[str, Any],
) -> list[RepresentationQualityIssue]:
    issues: list[RepresentationQualityIssue] = []
    filtering = bundle.filtering
    for field_name in ("discount_price_inr", "original_price_inr"):
        raw = record.get(field_name)
        if is_missing_value(raw):
            continue
        if isinstance(raw, bool):
            issues.append(
                _issue(
                    "price",
                    "invalid_price_type",
                    f"{field_name} must be an integer in canonical record",
                    field=field_name,
                )
            )
            continue
        if isinstance(raw, int):
            expected = raw
        elif isinstance(raw, float) and raw.is_integer():
            expected = int(raw)
        else:
            expected = None
        if expected is None or getattr(filtering, field_name) != expected:
            issues.append(
                _issue(
                    "price",
                    "price_not_preserved",
                    f"filtering.{field_name} must match canonical record",
                    field=field_name,
                )
            )
        if expected is not None and expected < 0:
            issues.append(
                _issue(
                    "price",
                    "negative_price",
                    f"{field_name} must be non-negative in filtering representation",
                    field=field_name,
                )
            )
    raw_anomaly = record.get("price_anomaly")
    if (
        not is_missing_value(raw_anomaly)
        and isinstance(raw_anomaly, bool)
        and filtering.price_anomaly is not raw_anomaly
    ):
        issues.append(
            _issue(
                "price",
                "price_anomaly_not_preserved",
                "filtering.price_anomaly must match canonical record",
                field="price_anomaly",
            )
        )
    raw_color = record.get("color_raw")
    if (
        not is_missing_value(raw_color)
        and isinstance(raw_color, str)
        and filtering.color_raw != raw_color.strip()
    ):
        issues.append(
            _issue(
                "color",
                "color_raw_not_preserved",
                "filtering.color_raw must match canonical color_raw",
                field="color_raw",
            )
        )
    raw_coded = record.get("color_is_coded")
    if (
        not is_missing_value(raw_coded)
        and isinstance(raw_coded, bool)
        and filtering.color_is_coded is not raw_coded
    ):
        issues.append(
            _issue(
                "color",
                "color_is_coded_not_preserved",
                "filtering.color_is_coded must match canonical record",
                field="color_is_coded",
            )
        )
    return issues


def _check_orchestration_consistency(
    bundle: ProductRepresentationBundle,
    record: Mapping[str, Any] | None,
) -> list[RepresentationQualityIssue]:
    issues: list[RepresentationQualityIssue] = []
    expected_text = build_product_text(bundle.product)
    if bundle.text != expected_text:
        issues.append(
            _issue(
                "consistency",
                "text_builder_mismatch",
                "bundle.text must match build_product_text(product)",
                field="text",
            )
        )
    if record is not None:
        expected_lexical = build_lexical_text_from_canonical(bundle.product, record)
        if bundle.lexical != expected_lexical:
            issues.append(
                _issue(
                    "consistency",
                    "lexical_builder_mismatch",
                    "bundle.lexical must match build_lexical_text_from_canonical(product, record)",
                    field="lexical",
                )
            )
        expected_semantic = build_semantic_text_from_canonical(bundle.product, record)
        if bundle.semantic != expected_semantic:
            issues.append(
                _issue(
                    "consistency",
                    "semantic_builder_mismatch",
                    "bundle.semantic must match build_semantic_text_from_canonical(product, record)",
                    field="semantic",
                )
            )
        expected_bundle = build_product_representation_bundle(record)
        if bundle.model_dump() != expected_bundle.model_dump():
            issues.append(
                _issue(
                    "consistency",
                    "nondeterministic_bundle",
                    "bundle must match a fresh pipeline generation for the same canonical record",
                )
            )
    return issues


def _check_structural(bundle: ProductRepresentationBundle) -> list[RepresentationQualityIssue]:
    issues: list[RepresentationQualityIssue] = []
    if not isinstance(bundle.product, ProductRepresentation):
        issues.append(
            _issue("structural", "invalid_product_type", "bundle.product must be ProductRepresentation")
        )
    if not isinstance(bundle.filtering, FilteringRepresentation):
        issues.append(
            _issue(
                "structural",
                "invalid_filtering_type",
                "bundle.filtering must be FilteringRepresentation",
            )
        )
    for field_name in _STRUCTURED_MULTI_VALUE_FIELDS:
        values = getattr(bundle.product, field_name)
        if values is None:
            continue
        for token in values:
            if token == "":
                issues.append(
                    _issue(
                        "structural",
                        "empty_multivalue_token",
                        f"product.{field_name} must not contain empty strings",
                        field=field_name,
                    )
                )
    return issues


def validate_product_representation_bundle(
    bundle: ProductRepresentationBundle,
    *,
    record: Mapping[str, Any] | None = None,
) -> RepresentationQualityReport:
    """Validate structural quality and cross-representation consistency (not retrieval relevance)."""
    if not isinstance(bundle, ProductRepresentationBundle):
        msg = "bundle must be a ProductRepresentationBundle"
        raise RepresentationQualityError(msg)

    issues: list[RepresentationQualityIssue] = []
    issues.extend(_check_structural(bundle))
    issues.extend(_check_degeneracy(bundle))
    issues.extend(_check_product_filtering_consistency(bundle.product, bundle.filtering))
    issues.extend(_check_preservation(bundle))
    issues.extend(_check_orchestration_consistency(bundle, record))
    if record is not None:
        issues.extend(_check_description(bundle, record))
        issues.extend(_check_prices_and_color_metadata(bundle, record))

    return _report_from_issues(issues)


def validate_canonical_record_representation_quality(
    record: Mapping[str, Any],
) -> RepresentationQualityReport:
    """Build a bundle via Phase 3.9 and validate it against the canonical record."""
    bundle = build_product_representation_bundle(record)
    return validate_product_representation_bundle(bundle, record=record)


def _bundle_field_populated(bundle: ProductRepresentationBundle, key: str) -> bool:
    if key == "brand":
        return bundle.product.brand is not None or bundle.product.brand_normalized is not None
    if key == "description":
        return "Description:" in bundle.semantic
    if key in MULTI_VALUE_REPRESENTATION_FIELDS:
        return getattr(bundle.product, key) is not None
    if key == "category_gender":
        return bool(bundle.product.category_gender.strip())
    return getattr(bundle.product, key) is not None


class _CatalogQualityAccumulator:
    """Incremental catalog metrics (one record at a time, no retained bundles/reports)."""

    def __init__(self) -> None:
        self.total_records = 0
        self.valid_records = 0
        self.degeneracy_issue_count = 0
        self.consistency_issue_count = 0
        self.total_issue_count = 0
        self._field_counts = {key: 0 for key in _FIELD_COVERAGE_KEYS}
        self._representation_counts = {key: 0 for key in _REPRESENTATION_COVERAGE_KEYS}

    def add(
        self,
        report: RepresentationQualityReport,
        bundle: ProductRepresentationBundle,
    ) -> None:
        self.total_records += 1
        if report.valid:
            self.valid_records += 1
        self.degeneracy_issue_count += report.degeneracy_issue_count
        self.consistency_issue_count += report.consistency_issue_count
        self.total_issue_count += report.issue_count

        self._representation_counts["filtering"] += 1
        for key in ("text", "lexical", "semantic"):
            if getattr(bundle, key).strip():
                self._representation_counts[key] += 1
        for key in _FIELD_COVERAGE_KEYS:
            if key == "description":
                if "Description:" in bundle.semantic:
                    self._field_counts[key] += 1
            elif _bundle_field_populated(bundle, key):
                self._field_counts[key] += 1

    def add_report_only(self, report: RepresentationQualityReport) -> None:
        self.total_records += 1
        if report.valid:
            self.valid_records += 1
        self.degeneracy_issue_count += report.degeneracy_issue_count
        self.consistency_issue_count += report.consistency_issue_count
        self.total_issue_count += report.issue_count

    def build(self) -> CatalogRepresentationQualityReport:
        total = self.total_records
        if total == 0:
            field_coverage = {key: 0.0 for key in _FIELD_COVERAGE_KEYS}
            representation_coverage = {key: 0.0 for key in _REPRESENTATION_COVERAGE_KEYS}
        else:
            field_coverage = {key: self._field_counts[key] / total for key in _FIELD_COVERAGE_KEYS}
            representation_coverage = {
                key: self._representation_counts[key] / total for key in _REPRESENTATION_COVERAGE_KEYS
            }
        return CatalogRepresentationQualityReport(
            total_records=total,
            valid_records=self.valid_records,
            invalid_records=total - self.valid_records,
            field_coverage=field_coverage,
            representation_coverage=representation_coverage,
            degeneracy_issue_count=self.degeneracy_issue_count,
            consistency_issue_count=self.consistency_issue_count,
            total_issue_count=self.total_issue_count,
        )


def summarize_representation_quality_reports(
    reports: Iterable[RepresentationQualityReport],
    *,
    bundles: Iterable[ProductRepresentationBundle] | None = None,
) -> CatalogRepresentationQualityReport:
    """Aggregate per-record reports into observational coverage metrics."""
    accumulator = _CatalogQualityAccumulator()
    if bundles is None:
        for report in reports:
            accumulator.add_report_only(report)
        return accumulator.build()

    for report, bundle in zip(reports, bundles, strict=True):
        accumulator.add(report, bundle)
    return accumulator.build()


def validate_canonical_records_representation_quality(
    records: Iterable[Mapping[str, Any]],
) -> CatalogRepresentationQualityReport:
    """Validate canonical records incrementally without retaining all bundles or reports."""
    accumulator = _CatalogQualityAccumulator()
    for record in records:
        bundle = build_product_representation_bundle(record)
        report = validate_product_representation_bundle(bundle, record=record)
        accumulator.add(report, bundle)
    return accumulator.build()


__all__ = [
    "CatalogRepresentationQualityReport",
    "RepresentationQualityIssue",
    "RepresentationQualityReport",
    "summarize_representation_quality_reports",
    "validate_canonical_record_representation_quality",
    "validate_canonical_records_representation_quality",
    "validate_product_representation_bundle",
]
