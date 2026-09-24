"""Smoke tests for package import and test environment setup."""

import productiq
from productiq.config import Settings, get_settings
from productiq.database import check_database_health, get_engine, session_scope
from productiq.exceptions import ProductIQError
from productiq.logging import get_logger


def test_package_is_importable() -> None:
    assert productiq.__name__ == "productiq"


def test_package_version_is_declared() -> None:
    assert productiq.__version__ == "0.1.0"


def test_core_public_api_is_importable() -> None:
    assert Settings is not None
    assert get_settings is not None
    assert ProductIQError is not None
    assert get_logger is not None
    assert get_engine is not None
    assert session_scope is not None
    assert check_database_health is not None
