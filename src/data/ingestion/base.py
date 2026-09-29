"""Abstract base interface for dataset loaders."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

import pandas as pd


class BaseDataLoader(ABC):
    """Common contract for loading raw datasets into pandas DataFrames."""

    @abstractmethod
    def load(self, path: Path) -> pd.DataFrame:
        """Load a raw dataset from the given filesystem path."""
