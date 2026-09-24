"""Tests for ProductIQ exception hierarchy."""

import pytest

from productiq.exceptions import (
    ConfigurationError,
    DatabaseError,
    PgvectorExtensionError,
    ProductIQError,
    ValidationError,
)


def test_productiq_error_can_be_raised() -> None:
    with pytest.raises(ProductIQError, match="base failure"):
        raise ProductIQError("base failure")


@pytest.mark.parametrize(
    ("exception_type", "message"),
    [
        (ConfigurationError, "invalid configuration"),
        (DatabaseError, "database unavailable"),
        (PgvectorExtensionError, "pgvector unavailable"),
        (ValidationError, "invalid input"),
    ],
)
def test_specialized_exceptions_inherit_from_productiq_error(
    exception_type: type[ProductIQError],
    message: str,
) -> None:
    with pytest.raises(exception_type) as exc_info:
        raise exception_type(message)

    raised = exc_info.value
    assert isinstance(raised, ProductIQError)
    assert str(raised) == message


def test_exceptions_remain_distinguishable_by_type() -> None:
    errors: list[ProductIQError] = [
        ConfigurationError("configuration"),
        DatabaseError("database"),
        PgvectorExtensionError("pgvector"),
        ValidationError("validation"),
    ]

    caught: list[type[ProductIQError]] = []
    for error in errors:
        try:
            raise error
        except ConfigurationError:
            caught.append(ConfigurationError)
        except PgvectorExtensionError:
            caught.append(PgvectorExtensionError)
        except DatabaseError:
            caught.append(DatabaseError)
        except ValidationError:
            caught.append(ValidationError)

    assert caught == [
        ConfigurationError,
        DatabaseError,
        PgvectorExtensionError,
        ValidationError,
    ]
