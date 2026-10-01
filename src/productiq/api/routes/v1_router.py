"""API v1 router aggregation."""

from __future__ import annotations

from fastapi import APIRouter

from productiq.api.routes.health import health_router
from productiq.api.routes.products import products_router
from productiq.api.routes.recommendations import recommendations_router
from productiq.api.routes.search import search_router

v1_router = APIRouter()
v1_router.include_router(health_router)
v1_router.include_router(search_router)
v1_router.include_router(recommendations_router)
v1_router.include_router(products_router)

__all__ = ["v1_router"]
