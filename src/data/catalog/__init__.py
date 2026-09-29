"""ProductIQ canonical catalog utilities."""

from __future__ import annotations

import importlib
from typing import Any

__all__ = [
    "AJIO_SOURCE_NAME",
    "CANONICAL_COLUMN_COUNT",
    "CANONICAL_COLUMN_ORDER",
    "CANONICAL_FIELD_DEFINITIONS",
    "REQUIRED_SOURCE_COLUMNS",
    "AjioCanonicalProductBuilder",
    "CanonicalBuildReport",
    "CanonicalBuildResult",
]


def _lazy(module: str, *names: str) -> dict[str, tuple[str, str]]:
    return {name: (module, name) for name in names}


_LAZY_EXPORTS: dict[str, tuple[str, str]] = {}
_LAZY_EXPORTS.update(
    _lazy(
        "data.catalog.schema",
        "AJIO_SOURCE_NAME",
        "CANONICAL_COLUMN_COUNT",
        "CANONICAL_COLUMN_ORDER",
        "CANONICAL_FIELD_DEFINITIONS",
        "REQUIRED_SOURCE_COLUMNS",
    )
)
_LAZY_EXPORTS.update(
    _lazy(
        "data.catalog.canonical",
        "AjioCanonicalProductBuilder",
        "CanonicalBuildReport",
        "CanonicalBuildResult",
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
