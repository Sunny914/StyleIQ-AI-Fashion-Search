"""Tests for AJIO raw data ingestion."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from data.ingestion import AjioDataLoader
from data.ingestion.ajio import AJIO_COLUMNS, AJIO_ENCODING
from productiq.exceptions import DataIngestionError, ProductIQError

PROJECT_ROOT = Path(__file__).resolve().parents[3]
AJIO_DATASET_PATH = PROJECT_ROOT / "resources" / "raw" / "Ajio Fashion Clothing.csv"

SAMPLE_CSV = """Product_URL,Brand,Description,Id_Product,URL_image,Category_by_gender,Discount Price (in Rs.),Original Price (in Rs.),Color
https://example.com/item,puma,Sample product,123456789001,https://example.com/image.jpg,Men,559,"1,499",white
"""


@pytest.fixture
def loader() -> AjioDataLoader:
    return AjioDataLoader()


@pytest.fixture
def sample_csv_path(tmp_path: Path) -> Path:
    dataset_path = tmp_path / "ajio_sample.csv"
    dataset_path.write_text(SAMPLE_CSV, encoding=AJIO_ENCODING)
    return dataset_path


def test_loads_sample_csv_successfully(loader: AjioDataLoader, sample_csv_path: Path) -> None:
    dataframe = loader.load(sample_csv_path)

    assert isinstance(dataframe, pd.DataFrame)
    assert len(dataframe) == 1
    assert list(dataframe.columns) == AJIO_COLUMNS


def test_missing_file_path_raises_data_ingestion_error(loader: AjioDataLoader, tmp_path: Path) -> None:
    missing_path = tmp_path / "missing.csv"

    with pytest.raises(DataIngestionError, match="does not exist"):
        loader.load(missing_path)


def test_directory_path_raises_data_ingestion_error(loader: AjioDataLoader, tmp_path: Path) -> None:
    with pytest.raises(DataIngestionError, match="not a file"):
        loader.load(tmp_path)


def test_uses_cp1252_encoding(loader: AjioDataLoader, sample_csv_path: Path) -> None:
    with patch("data.ingestion.ajio.pd.read_csv", wraps=pd.read_csv) as read_csv:
        loader.load(sample_csv_path)

    read_csv.assert_called_once_with(sample_csv_path, encoding=AJIO_ENCODING, dtype=str)


def test_raw_price_strings_remain_unchanged(loader: AjioDataLoader, sample_csv_path: Path) -> None:
    dataframe = loader.load(sample_csv_path)

    assert dataframe.loc[0, "Discount Price (in Rs.)"] == "559"
    assert dataframe.loc[0, "Original Price (in Rs.)"] == "1,499"


def test_no_accidental_transformation_during_ingestion(
    loader: AjioDataLoader,
    sample_csv_path: Path,
) -> None:
    dataframe = loader.load(sample_csv_path)

    assert dataframe.loc[0, "Brand"] == "puma"
    assert dataframe.loc[0, "Id_Product"] == "123456789001"
    assert dataframe["Discount Price (in Rs.)"].dtype == object
    assert dataframe["Original Price (in Rs.)"].dtype == object


def test_parser_failure_is_wrapped_in_data_ingestion_error(
    loader: AjioDataLoader,
    sample_csv_path: Path,
) -> None:
    with (
        patch("data.ingestion.ajio.pd.read_csv", side_effect=pd.errors.ParserError("bad csv")),
        pytest.raises(DataIngestionError, match="Failed to load AJIO dataset"),
    ):
        loader.load(sample_csv_path)


def test_data_ingestion_error_inherits_from_productiq_error() -> None:
    error = DataIngestionError("ingestion failed")

    assert isinstance(error, ProductIQError)


@pytest.mark.skipif(not AJIO_DATASET_PATH.is_file(), reason="AJIO raw dataset is unavailable")
def test_loads_full_ajio_dataset(loader: AjioDataLoader) -> None:
    dataframe = loader.load(AJIO_DATASET_PATH)

    assert len(dataframe) == 367_172
    assert len(dataframe.columns) == 9
    assert list(dataframe.columns) == AJIO_COLUMNS
    assert dataframe["Id_Product"].nunique() == 367_172
    assert dataframe.duplicated().sum() == 0
    assert dataframe.loc[1, "Original Price (in Rs.)"] == "1,499"
