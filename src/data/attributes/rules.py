"""Controlled vocabularies and deterministic attribute matching rules."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

import pandas as pd

from data.attributes.schema import MULTI_VALUE_DELIMITER, AttributeDefinition

WORD_BOUNDARY_LEFT = r"(?<![a-z0-9])"
WORD_BOUNDARY_RIGHT = r"(?![a-z0-9])"


@dataclass(frozen=True)
class VocabularyRule:
    """Maps source expressions to one canonical attribute value."""

    attribute: str
    canonical_value: str
    expressions: tuple[str, ...]


def normalize_attribute_text(value: object) -> str:
    """Normalize text for deterministic case-insensitive matching."""
    if value is None or value is pd.NA:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    if not isinstance(value, str):
        value = str(value)
    return re.sub(r"\s+", " ", value.lower().strip())


@lru_cache(maxsize=512)
def _expression_pattern(expression: str) -> re.Pattern[str]:
    normalized = normalize_attribute_text(expression)
    escaped = re.escape(normalized).replace(r"\ ", r"\s+")
    return re.compile(
        rf"{WORD_BOUNDARY_LEFT}{escaped}{WORD_BOUNDARY_RIGHT}",
        flags=re.IGNORECASE,
    )


def expression_matches(text: str, expression: str) -> bool:
    """Return whether a normalized expression matches within text."""
    if not text:
        return False
    return _expression_pattern(expression).search(text) is not None


ATTRIBUTE_VOCABULARY_RULES: tuple[VocabularyRule, ...] = (
    *(
        VocabularyRule("product_type", value, expressions)
        for value, expressions in (
            ("t_shirt", ("t-shirt", "t shirt")),
            ("sweatshirt", ("sweatshirt",)),
            ("track_pants", ("track pants",)),
            ("cargo_pants", ("cargo pants",)),
            ("night_suit", ("night suit",)),
            ("co_ord", ("co-ord", "coord")),
            ("kurta", ("kurta",)),
            ("saree", ("saree",)),
            ("dress", ("dress",)),
            ("jeans", ("jeans",)),
            ("trousers", ("trousers",)),
            ("shorts", ("shorts",)),
            ("skirt", ("skirt",)),
            ("jacket", ("jacket",)),
            ("hoodie", ("hoodie",)),
            ("top", ("top",)),
            ("blouse", ("blouse",)),
            ("camisole", ("camisole",)),
            ("tunic", ("tunic",)),
            ("leggings", ("leggings",)),
            ("joggers", ("joggers",)),
            ("blazer", ("blazer",)),
            ("sweater", ("sweater",)),
            ("cardigan", ("cardigan",)),
            ("palazzo", ("palazzo",)),
            ("kurti", ("kurti",)),
            ("shirt", ("shirt",)),
        )
    ),
    *(
        VocabularyRule("fit", value, expressions)
        for value, expressions in (
            ("slim_fit", ("slim fit",)),
            ("regular_fit", ("regular fit",)),
            ("relaxed_fit", ("relaxed fit",)),
            ("skinny_fit", ("skinny fit",)),
            ("straight_fit", ("straight fit",)),
            ("tailored_fit", ("tailored fit",)),
            ("tapered_fit", ("tapered fit",)),
            ("loose_fit", ("loose fit",)),
            ("comfort_fit", ("comfort fit",)),
            ("boxy_fit", ("boxy fit",)),
            ("oversized_fit", ("oversized fit", "oversized")),
        )
    ),
    *(
        VocabularyRule("pattern", value, expressions)
        for value, expressions in (
            ("floral", ("floral",)),
            ("printed", ("printed",)),
            ("striped", ("striped",)),
            ("graphic", ("graphic",)),
            ("solid", ("solid",)),
            ("checked", ("checked",)),
            ("typographic", ("typographic",)),
            ("embroidered", ("embroidered",)),
            ("textured", ("textured",)),
            ("geometric", ("geometric",)),
            ("abstract", ("abstract",)),
            ("polka", ("polka",)),
            ("colourblocked", ("colourblocked", "colorblocked")),
            ("self_design", ("self design", "self-design")),
            ("camouflage", ("camouflage",)),
            ("paisley", ("paisley",)),
            ("tie_dye", ("tie-dye", "tie dye")),
        )
    ),
    *(
        VocabularyRule("sleeve", value, expressions)
        for value, expressions in (
            ("full_sleeve", ("full sleeves", "full sleeve")),
            ("short_sleeve", ("short sleeves", "short sleeve")),
            ("sleeveless", ("sleeveless",)),
            ("half_sleeve", ("half sleeves", "half sleeve")),
            ("long_sleeve", ("long sleeves", "long sleeve")),
            ("three_quarter_sleeve", ("three quarter", "3/4 sleeve")),
            ("cap_sleeve", ("cap sleeve",)),
        )
    ),
    *(
        VocabularyRule("neckline", value, expressions)
        for value, expressions in (
            ("spread_collar", ("spread collar",)),
            ("mandarin_collar", ("mandarin collar",)),
            ("band_collar", ("band collar",)),
            ("v_neck", ("v-neck", "v neck")),
            ("round_neck", ("round neck",)),
            ("hooded", ("hooded",)),
            ("henley", ("henley",)),
            ("boat_neck", ("boat neck",)),
            ("high_neck", ("high neck",)),
            ("square_neck", ("square neck",)),
            ("collared", ("collared",)),
            ("polo_neck", ("polo neck",)),
        )
    ),
    *(
        VocabularyRule("material", value, expressions)
        for value, expressions in (
            ("cotton", ("cotton",)),
            ("silk", ("silk",)),
            ("georgette", ("georgette",)),
            ("denim", ("denim",)),
            ("linen", ("linen",)),
            ("chiffon", ("chiffon",)),
            ("satin", ("satin",)),
            ("crepe", ("crepe",)),
            ("wool", ("wool",)),
            ("fleece", ("fleece",)),
            ("viscose", ("viscose",)),
            ("rayon", ("rayon",)),
            ("polyester", ("polyester",)),
            ("nylon", ("nylon",)),
            ("leather", ("leather",)),
            ("velvet", ("velvet",)),
            ("spandex", ("spandex",)),
            ("lycra", ("lycra",)),
        )
    ),
    *(
        VocabularyRule("product_features", value, expressions)
        for value, expressions in (
            ("patch_pocket", ("patch pocket",)),
            ("kangaroo_pocket", ("kangaroo pocket",)),
            ("side_pocket", ("side pocket",)),
            ("chest_pocket", ("chest pocket",)),
            ("pocket", ("pocket",)),
            ("zip", ("zip",)),
            ("lace", ("lace",)),
            ("drawstring", ("drawstring",)),
            ("button", ("button",)),
            ("waistband", ("waistband",)),
            ("embroidery", ("embroidery",)),
            ("belt", ("belt",)),
            ("applique", ("applique",)),
            ("ruffles", ("ruffles",)),
            ("hood", ("hood",)),
        )
    ),
    *(
        VocabularyRule("style_attributes", value, expressions)
        for value, expressions in (
            ("a_line", ("a-line", "a line")),
            ("mid_rise", ("mid-rise", "mid rise")),
            ("high_rise", ("high-rise", "high rise")),
            ("low_rise", ("low-rise", "low rise")),
            ("flat_front", ("flat-front", "flat front")),
            ("ribbed", ("ribbed",)),
            ("panelled", ("panelled", "paneled")),
            ("distressed", ("distressed",)),
            ("bodycon", ("bodycon",)),
            ("cropped", ("cropped",)),
            ("pleated", ("pleated",)),
            ("oversized", ("oversized",)),
            ("ruched", ("ruched",)),
        )
    ),
)


def _rules_for_attribute(attribute: str) -> tuple[VocabularyRule, ...]:
    rules = [rule for rule in ATTRIBUTE_VOCABULARY_RULES if rule.attribute == attribute]
    return tuple(
        sorted(
            rules,
            key=lambda rule: max(len(expression) for expression in rule.expressions),
            reverse=True,
        )
    )


def extract_single_valued_attribute(text: str, attribute: str) -> str | None:
    for rule in _rules_for_attribute(attribute):
        for expression in sorted(rule.expressions, key=len, reverse=True):
            if expression_matches(text, expression):
                return rule.canonical_value
    return None


def extract_multi_valued_attribute(text: str, attribute: str) -> str | None:
    matched_values: list[str] = []
    for rule in _rules_for_attribute(attribute):
        for expression in sorted(rule.expressions, key=len, reverse=True):
            if expression_matches(text, expression):
                if rule.canonical_value not in matched_values:
                    matched_values.append(rule.canonical_value)
                break
    if not matched_values:
        return None
    return MULTI_VALUE_DELIMITER.join(sorted(matched_values))


def extract_attribute_value(text: str, attribute: AttributeDefinition) -> str | None:
    if attribute.multi_valued:
        return extract_multi_valued_attribute(text, attribute.name)
    return extract_single_valued_attribute(text, attribute.name)
