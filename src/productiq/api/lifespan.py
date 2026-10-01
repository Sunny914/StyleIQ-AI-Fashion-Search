"""Application lifecycle boundary (Phase 13.2)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI


@asynccontextmanager
async def build_lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup/shutdown hook without loading retrieval or model resources."""
    from productiq.logging import get_logger

    logger = get_logger(__name__)
    app.state.is_running = True
    services = getattr(app.state, "application_services", None)
    configured = services.configured_service_names() if services is not None else ()
    logger.info(
        "ProductIQ API starting (api_version=%s, configured_services=%s)",
        app.state.serving_config.api_version,
        ",".join(configured) if configured else "none",
    )
    try:
        yield
    finally:
        app.state.is_running = False
        logger.info("ProductIQ API shutdown complete")


__all__ = ["build_lifespan"]
