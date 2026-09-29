"""Abstract base interface for dataset validators."""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd

from data.validation.results import ValidationReport


class BaseDataValidator(ABC):
    """Common contract for validating ingested datasets without mutation."""

    @abstractmethod
    def validate(self, dataframe: pd.DataFrame) -> ValidationReport:
        """Validate the given DataFrame and return a structured report."""
