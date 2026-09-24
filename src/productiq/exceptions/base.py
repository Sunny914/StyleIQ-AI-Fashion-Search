"""Base ProductIQ exception types."""


class ProductIQError(Exception):
    """Base exception for ProductIQ application errors."""


class ConfigurationError(ProductIQError):
    """Raised when configuration is invalid or unavailable."""


class DatabaseError(ProductIQError):
    """Raised when database operations fail."""


class CatalogLoadError(DatabaseError):
    """Raised when product catalog loading fails."""


class CatalogValidationError(DatabaseError):
    """Raised when product catalog database validation fails."""


class PgvectorExtensionError(DatabaseError):
    """Raised when pgvector support is unavailable in Python or PostgreSQL."""


class ValidationError(ProductIQError):
    """Raised when input or data validation fails."""


class DataIngestionError(ProductIQError):
    """Raised when raw data ingestion fails."""


class DataValidationError(ValidationError):
    """Raised when dataset validation cannot be performed."""


class DataCleaningError(ProductIQError):
    """Raised when dataset cleaning cannot be performed."""


class DataNormalizationError(ProductIQError):
    """Raised when dataset normalization cannot be performed."""


class DataDeduplicationError(ProductIQError):
    """Raised when dataset deduplication analysis cannot be performed."""


class DataCatalogError(ProductIQError):
    """Raised when canonical catalog construction cannot be performed."""


class DataAttributeError(ProductIQError):
    """Raised when product attribute engineering cannot be performed."""


class DataExportError(ProductIQError):
    """Raised when processed dataset export or validation cannot be performed."""
