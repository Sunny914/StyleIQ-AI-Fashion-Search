"""Create ProductIQ catalog tables from SQLAlchemy metadata."""

from __future__ import annotations

from typing import cast

from sqlalchemy import Table
from sqlalchemy.engine import Engine

from productiq.database.base import Base
from productiq.database.models.product import Product


def create_product_catalog_tables(engine: Engine, *, checkfirst: bool = True) -> None:
    """Create catalog tables for development and tests (no Alembic in Phase 2.10)."""
    products_table = cast(Table, Product.__table__)
    Base.metadata.create_all(engine, tables=[products_table], checkfirst=checkfirst)


__all__ = ["create_product_catalog_tables"]
