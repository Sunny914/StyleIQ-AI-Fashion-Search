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


class ProductRepresentationError(ValidationError):
    """Raised when structured product representation build or validation fails."""


class FilteringRepresentationError(ValidationError):
    """Raised when metadata/filtering representation build or validation fails."""


class QueryRepresentationError(ValidationError):
    """Raised when query representation build or validation fails."""


class RepresentationQualityError(ValidationError):
    """Raised when representation quality validation input is invalid."""


class RepresentationDatasetError(ValidationError):
    """Raised when representation dataset generation or validation fails."""


class RetrievalError(ValidationError):
    """Raised when retrieval contract validation fails."""


class LexicalRetrievalError(RetrievalError):
    """Raised when lexical indexing or tokenization input is invalid."""


class SemanticRetrievalError(RetrievalError):
    """Raised when semantic vector or similarity input is invalid."""
