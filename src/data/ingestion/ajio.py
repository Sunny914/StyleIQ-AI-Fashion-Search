"""AJIO raw dataset ingestion."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from data.ingestion.base import BaseDataLoader
from productiq.exceptions import DataIngestionError
from productiq.logging import get_logger

AJIO_ENCODING = "cp1252"
AJIO_COLUMNS = [
    "Product_URL",
    "Brand",
    "Description",
    "Id_Product",
    "URL_image",
    "Category_by_gender",
    "Discount Price (in Rs.)",
    "Original Price (in Rs.)",
    "Color",
]


class AjioDataLoader(BaseDataLoader):
    """Load the raw AJIO fashion clothing CSV without transformation."""

    def load(self, path: Path) -> pd.DataFrame:
        """Load the AJIO CSV from ``path`` using CP1252 encoding."""
        logger = get_logger(__name__)

        if not path.exists():
            msg = f"Dataset path does not exist: {path}"
            raise DataIngestionError(msg)

        if not path.is_file():
            msg = f"Dataset path is not a file: {path}"
            raise DataIngestionError(msg)

        try:
            dataframe = pd.read_csv(path, encoding=AJIO_ENCODING, dtype=str)
        except (OSError, UnicodeDecodeError, pd.errors.ParserError) as exc:
            msg = f"Failed to load AJIO dataset from {path}"
            raise DataIngestionError(msg) from exc

        logger.info(
            "Loaded AJIO dataset from %s with %s rows and %s columns",
            path,
            len(dataframe),
            len(dataframe.columns),
        )
        return dataframe
