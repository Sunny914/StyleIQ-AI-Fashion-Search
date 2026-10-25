"""PostgreSQL-backed product catalog read provider (Phase 15C)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from productiq.database.models.product import Product
from productiq.serving.product_schema import ProductCatalogReadModel


class PostgresProductCatalogReadProvider:
    """Lookup one catalog row by product_id using a short-lived SQLAlchemy session."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def get_product(self, product_id: str) -> ProductCatalogReadModel | None:
        session = self._session_factory()
        try:
            stmt = select(Product).where(Product.product_id == product_id)
            row = session.scalar(stmt)
            if row is None:
                return None
            return ProductCatalogReadModel(
                product_id=row.product_id,
                brand=row.brand,
                brand_normalized=row.brand_normalized,
                description=row.description,
                image_url=row.image_url,
                product_url=row.product_url,
                category_gender=row.category_gender,
                product_type=row.product_type,
            )
        finally:
            session.close()


__all__ = ["PostgresProductCatalogReadProvider"]
