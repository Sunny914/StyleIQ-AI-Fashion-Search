"""Fixtures for database integration tests."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine

from productiq.config.settings import Settings, get_settings
from productiq.database.catalog_ddl import create_product_catalog_tables


@pytest.fixture
def integration_settings() -> Settings:
    """Load application settings from the local environment and .env file."""
    get_settings.cache_clear()
    return get_settings()


@pytest.fixture
def integration_engine(integration_settings: Settings) -> Iterator[Engine]:
    """Create a dedicated SQLAlchemy engine for integration tests."""
    from productiq.database.engine import create_engine_from_settings

    engine = create_engine_from_settings(integration_settings)
    yield engine
    engine.dispose()


@pytest.fixture
def catalog_table(integration_engine: Engine) -> Iterator[None]:
    """Ensure the products table exists and truncate it after each test."""
    create_product_catalog_tables(integration_engine, checkfirst=True)
    yield None
    with integration_engine.begin() as connection:
        connection.execute(text("TRUNCATE TABLE products"))
