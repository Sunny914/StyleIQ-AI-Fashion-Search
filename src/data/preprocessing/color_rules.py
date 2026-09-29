"""Color normalization helpers for AJIO datasets."""

from __future__ import annotations

import re

SAFE_SHORT_COLOR_TOKENS = frozenset(
    {
        "aqua",
        "ash",
        "beige",
        "berry",
        "black",
        "blue",
        "blush",
        "brown",
        "burgundy",
        "camel",
        "charcoal",
        "copper",
        "coral",
        "cream",
        "crimson",
        "denim",
        "ecru",
        "gold",
        "gray",
        "green",
        "grey",
        "indigo",
        "ivory",
        "khaki",
        "lime",
        "maroon",
        "mint",
        "mauve",
        "multi",
        "mustard",
        "navy",
        "nude",
        "olive",
        "orange",
        "peach",
        "petrol",
        "pink",
        "plum",
        "purple",
        "red",
        "rose",
        "rust",
        "sage",
        "sand",
        "skin",
        "sky",
        "slate",
        "snow",
        "stone",
        "tan",
        "teal",
        "turquoise",
        "wine",
        "yellow",
    }
)

ATOMIC_COLOR_TOKENS = SAFE_SHORT_COLOR_TOKENS | {
    "assorted",
    "melange",
    "melege",
    "charcoal",
    "burgundy",
    "turquoise",
    "anthracite",
    "fuchsia",
    "magenta",
    "multicolour",
}

COLOR_MODIFIER_PREFIXES = (
    "lightgrey",
    "lightgray",
    "lightgreen",
    "lightblue",
    "lightpink",
    "lightbrown",
    "lightpurple",
    "lightyellow",
    "darkblue",
    "darkgreen",
    "darkgrey",
    "darkgray",
    "darkkhaki",
    "darkolive",
    "darkbrown",
    "darkpink",
    "darkred",
    "darkpurple",
    "darkyellow",
    "darkwine",
    "darknavy",
    "darkteal",
    "darkmaroon",
    "darkburgundy",
    "mediumblue",
    "mediumgrey",
    "mediumgray",
    "mediumgreen",
    "medgrey",
    "medgray",
    "medblue",
    "medgreen",
    "ltblue",
    "ltpink",
    "ltgrey",
    "ltgray",
    "ltgreen",
    "ltyellow",
    "ltpurple",
    "ltaqua",
    "ltpeach",
    "ltbrown",
    "navyblue",
    "offwhite",
    "olivegreen",
    "indigoblue",
    "jetblack",
    "mintgreen",
    "steelgrey",
    "steelgray",
    "midgrey",
    "midgray",
    "gunmetal",
    "blackcharcoal",
    "blackgrey",
    "blackgray",
    "blackwhite",
    "aquablue",
    "maroonburg",
    "royalblue",
    "limegreen",
    "lightgreymelange",
    "charcoalmelange",
    "navymelange",
    "blackmelange",
    "anthramelange",
    "antramelange",
    "bluemelange",
    "greymelange",
    "ecrumelange",
    "bluemelege",
    "blackglgrey",
    "petrolblue",
    "magntafusha",
)

SPLIT_PREFIXES = sorted(
    {
        *COLOR_MODIFIER_PREFIXES,
        "light",
        "dark",
        "medium",
        "med",
        "lt",
        "off",
        "navy",
        "black",
        "olive",
        "aqua",
        "steel",
        "jet",
        "mint",
        "lime",
        "ecru",
        "indigo",
        "maroon",
        "petrol",
        "gun",
        "royal",
        "charcoal",
        "anthracite",
        "turquoise",
        "burgundy",
        "mustard",
        "yellow",
        "orange",
        "purple",
        "pink",
        "green",
        "brown",
        "beige",
        "gold",
        "tan",
        "grey",
        "gray",
        "blue",
        "white",
        "red",
        "wine",
        "nude",
        "sky",
        "teal",
        "rust",
        "coral",
        "khaki",
        "stone",
        "cream",
        "peach",
        "sand",
        "mauve",
        "plum",
        "sage",
        "copper",
        "bronze",
        "ivory",
        "lilac",
        "berry",
        "denim",
        "camel",
        "ash",
        "snow",
        "coal",
        "ink",
        "taupe",
        "vanilla",
        "lemon",
        "emerald",
        "sapphire",
        "ruby",
        "amber",
    },
    key=len,
    reverse=True,
)

ATOMIC_MODIFIER_PREFIXES = frozenset({"medium"})
_MELANGE_SUFFIX_PATTERN = re.compile(r"melange$")
_MELEGE_SUFFIX_PATTERN = re.compile(r"melege$")
_MELANGED_SUFFIX_PATTERN = re.compile(r"melanged$")


def is_coded_color(value: str) -> bool:
    """Return whether a color value should be treated as opaque/catalog-coded."""
    lower = value.lower().strip()
    if not lower:
        return False
    if re.search(r"\d", lower):
        return True
    if len(lower) <= 4:
        return lower not in SAFE_SHORT_COLOR_TOKENS
    return False


def normalize_color_value(value: str) -> tuple[str, bool]:
    """Normalize a color token mechanically without guessing coded values."""
    if not isinstance(value, str):
        return value, False

    original = value
    lower = value.lower().strip()
    if not lower:
        return original, False

    if is_coded_color(lower):
        return original, True

    normalized = lower
    if normalized == "gray":
        normalized = "grey"
    elif normalized == "multicolour":
        normalized = "multi_colour"

    if _MELANGED_SUFFIX_PATTERN.search(normalized):
        return lower, False

    melange_match = _MELANGE_SUFFIX_PATTERN.search(normalized)
    if melange_match and len(normalized) > len("melange"):
        base = normalized[: melange_match.start()]
        if base:
            normalized = f"{_split_color_compound(base)}_melange"
            return normalized, False

    melege_match = _MELEGE_SUFFIX_PATTERN.search(normalized)
    if melege_match and len(normalized) > len("melege"):
        base = normalized[: melege_match.start()]
        if base:
            normalized = f"{_split_color_compound(base)}_melege"
            return normalized, False

    normalized = _split_color_compound(normalized)
    return normalized, False


def _split_color_compound(lower: str) -> str:
    if lower in ATOMIC_COLOR_TOKENS:
        return "grey" if lower == "gray" else lower

    for prefix in SPLIT_PREFIXES:
        if lower == prefix:
            return _split_known_modifier(prefix)

        if lower.startswith(prefix) and len(lower) > len(prefix):
            rest = lower[len(prefix) :]
            if rest:
                left = _split_known_modifier(prefix) if lower != prefix else prefix
                if left == prefix:
                    left = "grey" if prefix == "gray" else prefix
                return f"{left}_{_split_color_compound(rest)}"

    return lower


def _split_known_modifier(prefix: str) -> str:
    if prefix in ATOMIC_COLOR_TOKENS:
        return "grey" if prefix == "gray" else prefix

    if prefix in ATOMIC_MODIFIER_PREFIXES:
        return "grey" if prefix == "gray" else prefix

    for split_prefix in SPLIT_PREFIXES:
        if prefix.startswith(split_prefix) and len(prefix) > len(split_prefix):
            rest = prefix[len(split_prefix) :]
            if rest:
                left = "grey" if split_prefix == "gray" else split_prefix
                return f"{left}_{_split_color_compound(rest)}"

    return "grey" if prefix == "gray" else prefix
