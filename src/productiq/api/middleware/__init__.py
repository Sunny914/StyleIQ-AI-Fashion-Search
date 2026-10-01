"""HTTP middleware for the FastAPI adapter."""

from productiq.api.middleware.request_id import RequestIdMiddleware

__all__ = ["RequestIdMiddleware"]
