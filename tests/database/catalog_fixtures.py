"""Synthetic catalog records for database tests."""

from __future__ import annotations

from typing import Any


def make_product_record(**overrides: object) -> dict[str, Any]:
    record: dict[str, Any] = {
        "product_id": "123456789001",
        "product_url": "https://example.com/a",
        "brand": "puma",
        "brand_normalized": "puma",
        "description": "Striped Slim Fit Shirt with Patch Pocket",
        "image_url": "https://example.com/img",
        "category_gender": "Men",
        "color_raw": "blue",
        "color_normalized": "blue",
        "color_is_coded": False,
        "discount_price_inr": 559,
        "original_price_inr": 999,
        "price_anomaly": False,
        "source": "ajio",
        "product_type": "shirt",
        "fit": "slim_fit",
        "pattern": "striped",
        "sleeve": None,
        "neckline": None,
        "material": None,
        "product_features": "patch_pocket|pocket",
        "style_attributes": None,
    }
    record.update(overrides)
    return record


def make_product_records(count: int = 2) -> list[dict[str, Any]]:
    records = [make_product_record()]
    for index in range(1, count):
        records.append(make_product_record(product_id=f"12345678900{index + 1}"))
    return records
