"""HTTP-layer exception types (Phase 13.2)."""

from __future__ import annotations

from productiq.exceptions.base import ProductIQError


class ApiNotFoundError(ProductIQError):
    """Raised when a requested API resource does not exist."""


__all__ = ["ApiNotFoundError"]
