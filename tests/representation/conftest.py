"""Fixtures for representation tests."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tests.database.catalog_fixtures import make_product_record


@pytest.fixture
def canonical_record() -> dict[str, Any]:
    return make_product_record()


@pytest.fixture
def processed_parquet_path() -> Path:
    root = Path(__file__).resolve().parents[2]
    path = root / "resources" / "processed" / "product_catalog.parquet"
    if not path.is_file():
        pytest.skip("processed product catalog parquet not available")
    return path
