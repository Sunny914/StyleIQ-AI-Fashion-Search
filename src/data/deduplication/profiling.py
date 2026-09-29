"""Read-only duplication profiling for prepared AJIO datasets."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from data.ingestion.ajio import AJIO_COLUMNS
from data.preprocessing.cleaning import PRICE_ANOMALY_COLUMN
from data.preprocessing.normalization import COLOR_NORMALIZED_COLUMN
from productiq.exceptions import DataDeduplicationError
from productiq.logging import get_logger

PRODUCT_URL_COLUMN = "Product_URL"
URL_IMAGE_COLUMN = "URL_image"
ID_PRODUCT_COLUMN = "Id_Product"

CANDIDATE_DUPLICATE_KEYS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "brand_description_category_color",
        ("Brand", "Description", "Category_by_gender", "Color"),
    ),
    (
        "brand_description_category_color_prices",
        (
            "Brand",
            "Description",
            "Category_by_gender",
            "Color",
            "Discount Price (in Rs.)",
            "Original Price (in Rs.)",
        ),
    ),
    (
        "brand_description_category",
        ("Brand", "Description", "Category_by_gender"),
    ),
    (
        "brand_description_color",
        ("Brand", "Description", "Color"),
    ),
)


@dataclass(frozen=True)
class DuplicateValueSummary:
    """Duplicate analysis for a single-column identity field."""

    column: str
    duplicate_value_count: int
    rows_in_duplicate_values: int
    largest_group_size: int


@dataclass(frozen=True)
class UrlDuplicateVarianceSummary:
    """How duplicate Product_URL groups vary across selected fields."""

    groups_with_multiple_rows: int
    groups_with_multiple_id_product: int
    groups_with_multiple_brand: int
    groups_with_multiple_description: int
    groups_with_multiple_color: int
    groups_with_multiple_url_image: int
    groups_with_multiple_discount_price: int
    groups_with_multiple_original_price: int
    groups_with_multiple_category: int


@dataclass(frozen=True)
class CandidateKeySummary:
    """Duplicate analysis for a composite business key."""

    key_name: str
    key_columns: tuple[str, ...]
    unique_keys: int
    duplicated_keys: int
    rows_in_duplicated_groups: int
    largest_group_size: int
    example_group_keys: tuple[tuple[str, ...], ...]


@dataclass(frozen=True)
class RepresentativeDuplicateGroup:
    """Small sample of rows from one duplicated group."""

    grouping_label: str
    group_key: tuple[str, ...]
    row_count: int
    distinct_id_product_count: int
    distinct_product_url_count: int
    distinct_url_image_count: int
    sample_id_products: tuple[str, ...]
    sample_product_urls: tuple[str, ...]


@dataclass(frozen=True)
class DuplicationProfile:
    """Structured duplication analysis for one prepared dataset."""

    total_rows: int
    exact_duplicate_rows: int
    exact_duplicate_groups: int
    id_product_duplicate_rows: int
    id_product_duplicate_values: int
    product_url_summary: DuplicateValueSummary
    url_image_summary: DuplicateValueSummary
    product_url_variance: UrlDuplicateVarianceSummary
    candidate_keys: tuple[CandidateKeySummary, ...]
    representative_groups: tuple[RepresentativeDuplicateGroup, ...]

    def summary(self) -> str:
        """Return a human-readable duplication profile summary."""
        lines = [
            f"Total rows: {self.total_rows}",
            f"Exact duplicate rows: {self.exact_duplicate_rows}",
            f"Exact duplicate groups: {self.exact_duplicate_groups}",
            f"Duplicate Id_Product rows: {self.id_product_duplicate_rows}",
            f"Duplicate Id_Product values: {self.id_product_duplicate_values}",
            (
                "Duplicate Product_URL values: "
                f"{self.product_url_summary.duplicate_value_count} "
                f"({self.product_url_summary.rows_in_duplicate_values} rows)"
            ),
            (
                "Duplicate URL_image values: "
                f"{self.url_image_summary.duplicate_value_count} "
                f"({self.url_image_summary.rows_in_duplicate_values} rows)"
            ),
        ]
        for candidate in self.candidate_keys:
            lines.append(
                
                    f"{candidate.key_name}: duplicated_keys="
                    f"{candidate.duplicated_keys}, rows_in_duplicated_groups="
                    f"{candidate.rows_in_duplicated_groups}, largest_group="
                    f"{candidate.largest_group_size}"
                
            )
        return "\n".join(lines)


class AjioDuplicationProfiler:
    """Profile duplication patterns without modifying the input DataFrame."""

    def profile(self, dataframe: pd.DataFrame) -> DuplicationProfile:
        """Analyze duplication patterns and return a structured profile."""
        logger = get_logger(__name__)

        if not isinstance(dataframe, pd.DataFrame):
            msg = "Duplication profiling input must be a pandas DataFrame"
            raise DataDeduplicationError(msg)

        required_columns = (
            *AJIO_COLUMNS,
            "Discount Price (in Rs.)",
            "Original Price (in Rs.)",
            PRICE_ANOMALY_COLUMN,
            COLOR_NORMALIZED_COLUMN,
        )
        missing_columns = [column for column in required_columns if column not in dataframe.columns]
        if missing_columns:
            msg = f"Missing required columns for duplication profiling: {', '.join(missing_columns)}"
            raise DataDeduplicationError(msg)

        total_rows = len(dataframe)
        exact_duplicate_rows = int(dataframe.duplicated().sum())
        if exact_duplicate_rows:
            exact_duplicate_groups = int(
                dataframe[dataframe.duplicated(keep=False)]
                .groupby(list(dataframe.columns), dropna=False)
                .ngroups
            )
        else:
            exact_duplicate_groups = 0

        id_duplicate_mask = dataframe[ID_PRODUCT_COLUMN].duplicated(keep=False)
        id_product_duplicate_rows = int(id_duplicate_mask.sum())
        id_product_duplicate_values = int(dataframe.loc[id_duplicate_mask, ID_PRODUCT_COLUMN].nunique())

        product_url_summary = self._duplicate_value_summary(dataframe, PRODUCT_URL_COLUMN)
        url_image_summary = self._duplicate_value_summary(dataframe, URL_IMAGE_COLUMN)
        product_url_variance = self._product_url_variance_summary(dataframe)
        candidate_keys = tuple(
            self._candidate_key_summary(dataframe, key_name, key_columns)
            for key_name, key_columns in CANDIDATE_DUPLICATE_KEYS
        )
        representative_groups = self._representative_groups(dataframe, candidate_keys)

        profile = DuplicationProfile(
            total_rows=total_rows,
            exact_duplicate_rows=exact_duplicate_rows,
            exact_duplicate_groups=exact_duplicate_groups,
            id_product_duplicate_rows=id_product_duplicate_rows,
            id_product_duplicate_values=id_product_duplicate_values,
            product_url_summary=product_url_summary,
            url_image_summary=url_image_summary,
            product_url_variance=product_url_variance,
            candidate_keys=candidate_keys,
            representative_groups=representative_groups,
        )
        logger.info(
            "Completed AJIO duplication profiling for %s rows (%s exact duplicate rows)",
            profile.total_rows,
            profile.exact_duplicate_rows,
        )
        return profile

    def _duplicate_value_summary(
        self,
        dataframe: pd.DataFrame,
        column: str,
    ) -> DuplicateValueSummary:
        counts = dataframe[column].value_counts(dropna=False)
        duplicated = counts[counts > 1]
        rows_in_duplicate_values = int(duplicated.sum()) if not duplicated.empty else 0
        largest_group_size = int(duplicated.max()) if not duplicated.empty else 0
        return DuplicateValueSummary(
            column=column,
            duplicate_value_count=len(duplicated),
            rows_in_duplicate_values=rows_in_duplicate_values,
            largest_group_size=largest_group_size,
        )

    def _product_url_variance_summary(self, dataframe: pd.DataFrame) -> UrlDuplicateVarianceSummary:
        duplicate_url_counts = dataframe[PRODUCT_URL_COLUMN].value_counts()
        duplicate_url_values = duplicate_url_counts[duplicate_url_counts > 1].index
        duplicate_groups = dataframe[dataframe[PRODUCT_URL_COLUMN].isin(duplicate_url_values)].groupby(
            PRODUCT_URL_COLUMN,
            dropna=False,
        )

        metrics = {
            "groups_with_multiple_rows": 0,
            "groups_with_multiple_id_product": 0,
            "groups_with_multiple_brand": 0,
            "groups_with_multiple_description": 0,
            "groups_with_multiple_color": 0,
            "groups_with_multiple_url_image": 0,
            "groups_with_multiple_discount_price": 0,
            "groups_with_multiple_original_price": 0,
            "groups_with_multiple_category": 0,
        }

        for _, group in duplicate_groups:
            metrics["groups_with_multiple_rows"] += 1
            if group[ID_PRODUCT_COLUMN].nunique(dropna=False) > 1:
                metrics["groups_with_multiple_id_product"] += 1
            if group["Brand"].nunique(dropna=False) > 1:
                metrics["groups_with_multiple_brand"] += 1
            if group["Description"].nunique(dropna=False) > 1:
                metrics["groups_with_multiple_description"] += 1
            if group["Color"].nunique(dropna=False) > 1:
                metrics["groups_with_multiple_color"] += 1
            if group[URL_IMAGE_COLUMN].nunique(dropna=False) > 1:
                metrics["groups_with_multiple_url_image"] += 1
            if group["Discount Price (in Rs.)"].nunique(dropna=False) > 1:
                metrics["groups_with_multiple_discount_price"] += 1
            if group["Original Price (in Rs.)"].nunique(dropna=False) > 1:
                metrics["groups_with_multiple_original_price"] += 1
            if group["Category_by_gender"].nunique(dropna=False) > 1:
                metrics["groups_with_multiple_category"] += 1

        return UrlDuplicateVarianceSummary(**metrics)

    def _candidate_key_summary(
        self,
        dataframe: pd.DataFrame,
        key_name: str,
        key_columns: tuple[str, ...],
    ) -> CandidateKeySummary:
        grouped = dataframe.groupby(list(key_columns), dropna=False).size().reset_index(name="row_count")
        duplicated = grouped[grouped["row_count"] > 1]
        rows_in_duplicated_groups = int(duplicated["row_count"].sum()) if not duplicated.empty else 0
        largest_group_size = int(duplicated["row_count"].max()) if not duplicated.empty else 0
        example_rows = duplicated.sort_values("row_count", ascending=False).head(3)
        example_group_keys = tuple(
            tuple(str(row[column]) for column in key_columns) for _, row in example_rows.iterrows()
        )
        return CandidateKeySummary(
            key_name=key_name,
            key_columns=key_columns,
            unique_keys=int(grouped.shape[0]),
            duplicated_keys=len(duplicated),
            rows_in_duplicated_groups=rows_in_duplicated_groups,
            largest_group_size=largest_group_size,
            example_group_keys=example_group_keys,
        )

    def _representative_groups(
        self,
        dataframe: pd.DataFrame,
        candidate_keys: tuple[CandidateKeySummary, ...],
    ) -> tuple[RepresentativeDuplicateGroup, ...]:
        representatives: list[RepresentativeDuplicateGroup] = []
        priority_key = next(
            (candidate for candidate in candidate_keys if candidate.duplicated_keys > 0),
            None,
        )
        if priority_key is None:
            return ()

        grouped = (
            dataframe.groupby(list(priority_key.key_columns), dropna=False)
            .size()
            .reset_index(name="row_count")
            .sort_values("row_count", ascending=False)
        )
        duplicated = grouped[grouped["row_count"] > 1].head(3)

        for _, duplicate_key_row in duplicated.iterrows():
            mask = pd.Series(True, index=dataframe.index)
            for column in priority_key.key_columns:
                mask &= dataframe[column] == duplicate_key_row[column]
            group = dataframe.loc[mask]
            group_key = tuple(str(duplicate_key_row[column]) for column in priority_key.key_columns)
            representatives.append(
                RepresentativeDuplicateGroup(
                    grouping_label=priority_key.key_name,
                    group_key=group_key,
                    row_count=int(duplicate_key_row["row_count"]),
                    distinct_id_product_count=int(group[ID_PRODUCT_COLUMN].nunique()),
                    distinct_product_url_count=int(group[PRODUCT_URL_COLUMN].nunique()),
                    distinct_url_image_count=int(group[URL_IMAGE_COLUMN].nunique()),
                    sample_id_products=tuple(group[ID_PRODUCT_COLUMN].head(3).astype(str).tolist()),
                    sample_product_urls=tuple(group[PRODUCT_URL_COLUMN].head(3).astype(str).tolist()),
                )
            )

        return tuple(representatives)
