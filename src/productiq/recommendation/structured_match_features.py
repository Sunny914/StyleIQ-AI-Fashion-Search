"""Structured match feature propagation (Phase 11.4)."""

from __future__ import annotations

from productiq.recommendation.feature_schema import StructuredMatchFeatureGroup
from productiq.recommendation.similarity_schema import ContentSimilarity


def extract_structured_match_features(similarity: ContentSimilarity) -> StructuredMatchFeatureGroup:
    """Map Phase 11.3 structured similarities to recommendation feature names."""
    scalars = similarity.structured.scalars
    multivalue = similarity.structured.multivalue
    return StructuredMatchFeatureGroup(
        brand_match=scalars.brand,
        brand_normalized_match=scalars.brand_normalized,
        category_gender_match=scalars.category_gender,
        product_type_match=scalars.product_type,
        color_overlap=multivalue.color,
        pattern_overlap=multivalue.pattern,
        material_overlap=multivalue.material,
        fit_overlap=multivalue.fit,
        sleeve_overlap=multivalue.sleeve,
        neckline_overlap=multivalue.neckline,
        product_features_overlap=multivalue.product_features,
        style_attributes_overlap=multivalue.style_attributes,
    )


__all__ = ["extract_structured_match_features"]
