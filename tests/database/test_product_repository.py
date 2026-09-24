"""Unit tests for ProductRepository."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from productiq.database.base import Base
from productiq.database.models.product import Product
from productiq.database.repository import ProductRepository
from tests.database.catalog_fixtures import make_product_record


@pytest.fixture
def repository_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[Product.__table__])
    session = sessionmaker(bind=engine)()
    session.add(Product(**make_product_record()))
    session.add(
        Product(
            **make_product_record(
                product_id="123456789002",
                brand_normalized="nike",
                category_gender="Women",
                color_normalized="red",
            )
        )
    )
    session.commit()
    yield session
    session.close()
    engine.dispose()


def test_get_by_id_returns_product(repository_session: Session) -> None:
    repository = ProductRepository(repository_session)

    product = repository.get_by_id("123456789001")

    assert product is not None
    assert product.product_id == "123456789001"


def test_find_by_brand_supports_pagination(repository_session: Session) -> None:
    repository = ProductRepository(repository_session)

    nike_products = repository.find_by_brand("nike", limit=10, offset=0)

    assert len(nike_products) == 1
    assert nike_products[0].brand_normalized == "nike"


def test_find_by_category_and_color(repository_session: Session) -> None:
    repository = ProductRepository(repository_session)

    products = repository.find_filtered(
        category_gender="Women",
        color_normalized="red",
        limit=5,
        offset=0,
    )

    assert len(products) == 1
    assert products[0].product_id == "123456789002"


def test_count_returns_total_rows(repository_session: Session) -> None:
    repository = ProductRepository(repository_session)

    assert repository.count() == 2


def test_pagination_limit_must_be_positive(repository_session: Session) -> None:
    repository = ProductRepository(repository_session)

    with pytest.raises(ValueError, match="limit must be positive"):
        repository.find_by_brand("puma", limit=0)
