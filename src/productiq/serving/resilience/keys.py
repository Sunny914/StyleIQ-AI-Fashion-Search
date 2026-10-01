"""Rate-limit key derivation (Phase 13.10-B)."""

from __future__ import annotations

import hashlib

from starlette.requests import Request


def resolve_client_identifier(request: Request, *, trust_forwarded_for: bool) -> str:
    """Bounded client identifier for rate limiting (never logged raw)."""
    if trust_forwarded_for:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            candidate = forwarded.split(",")[0].strip()
            if candidate:
                return candidate[:64]
    if request.client is not None and request.client.host:
        return request.client.host[:64]
    return "anonymous"


def build_rate_limit_key(
    request: Request,
    *,
    deployment_key: str,
    trust_forwarded_for: bool = False,
) -> str:
    """Stable hashed key for in-memory rate limiting."""
    client_id = resolve_client_identifier(request, trust_forwarded_for=trust_forwarded_for)
    material = f"{deployment_key}|{client_id}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


__all__ = ["build_rate_limit_key", "resolve_client_identifier"]
