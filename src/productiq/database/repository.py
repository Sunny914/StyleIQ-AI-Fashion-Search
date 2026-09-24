"""Product catalog repository / data-access layer."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from productiq.database.models.product import Product


class ProductRepository:
    """SQLAlchemy-backed access to ProductIQ catalog rows."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_id(self, product_id: str) -> Product | None:
        """Return one product by stable catalog identity."""
        return self._session.get(Product, product_id)

    def find_by_brand(
        self,
        brand_normalized: str,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Product]:
        """Return products for a normalized brand with pagination."""
        _validate_pagination(limit=limit, offset=offset)
        stmt = (
            select(Product)
            .where(Product.brand_normalized == brand_normalized)
            .order_by(Product.product_id)
            .limit(limit)
            .offset(offset)
        )
        return list(self._session.scalars(stmt))

    def find_by_category(
        self,
        category_gender: str,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Product]:
        """Return products for a category/gender value with pagination."""
        _validate_pagination(limit=limit, offset=offset)
        stmt = (
            select(Product)
            .where(Product.category_gender == category_gender)
            .order_by(Product.product_id)
            .limit(limit)
            .offset(offset)
        )
        return list(self._session.scalars(stmt))

    def find_by_color(
        self,
        color_normalized: str,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Product]:
        """Return products for a normalized color with pagination."""
        _validate_pagination(limit=limit, offset=offset)
        stmt = (
            select(Product)
            .where(Product.color_normalized == color_normalized)
            .order_by(Product.product_id)
            .limit(limit)
            .offset(offset)
        )
        return list(self._session.scalars(stmt))

    def find_filtered(
        self,
        *,
        brand_normalized: str | None = None,
        category_gender: str | None = None,
        color_normalized: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Product]:
        """Return products matching optional filters with pagination."""
        _validate_pagination(limit=limit, offset=offset)
        stmt = select(Product)
        if brand_normalized is not None:
            stmt = stmt.where(Product.brand_normalized == brand_normalized)
        if category_gender is not None:
            stmt = stmt.where(Product.category_gender == category_gender)
        if color_normalized is not None:
            stmt = stmt.where(Product.color_normalized == color_normalized)
        stmt = stmt.order_by(Product.product_id).limit(limit).offset(offset)
        return list(self._session.scalars(stmt))

    def count(self) -> int:
        """Return total product count."""
        total = self._session.scalar(select(func.count()).select_from(Product))
        return int(total or 0)


def _validate_pagination(*, limit: int, offset: int) -> None:
    if limit <= 0:
        msg = "Repository pagination limit must be positive"
        raise ValueError(msg)
    if offset < 0:
        msg = "Repository pagination offset must be non-negative"
        raise ValueError(msg)


__all__ = ["ProductRepository"]
