"""Shared pytest fixtures for ProductIQ tests."""

import pytest

from productiq.config.settings import get_settings
from productiq.database.engine import reset_database_state
from productiq.database.session import reset_session_factory
from productiq.logging.setup import reset_logging_configuration


@pytest.fixture(autouse=True)
def reset_application_state() -> None:
    """Reset cached settings and logging between tests for isolation."""
    get_settings.cache_clear()
    reset_logging_configuration()
    reset_database_state()
    reset_session_factory()
    yield
    get_settings.cache_clear()
    reset_logging_configuration()
    reset_database_state()
    reset_session_factory()
