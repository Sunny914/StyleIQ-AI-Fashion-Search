"""Request-scoped context for the HTTP adapter (Phase 13.2)."""

from __future__ import annotations

from contextvars import ContextVar

_request_id_var: ContextVar[str | None] = ContextVar("productiq_request_id", default=None)


def set_request_id(request_id: str) -> None:
    _request_id_var.set(request_id)


def get_request_id() -> str | None:
    return _request_id_var.get()


def clear_request_id() -> None:
    _request_id_var.set(None)


__all__ = [
    "clear_request_id",
    "get_request_id",
    "set_request_id",
]
