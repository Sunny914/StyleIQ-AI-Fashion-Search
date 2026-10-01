"""Shared fixtures for API and integration tests (Phase 13.7)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from productiq.api.app import create_app
from productiq.api.services.application_services import ApplicationServices
from tests.api.test_application_integration import _integrated_services


@pytest.fixture
def integrated_services() -> ApplicationServices:
    """Deterministic in-memory search, recommendation, and product services."""
    return _integrated_services()


@pytest.fixture
def integrated_app(integrated_services: ApplicationServices):
    return create_app(application_services=integrated_services)


@pytest.fixture
def integrated_client(integrated_app) -> TestClient:
    with TestClient(integrated_app) as client:
        yield client


__all__ = ["integrated_app", "integrated_client", "integrated_services"]
