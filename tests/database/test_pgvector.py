"""Unit tests for pgvector foundation."""

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import SQLAlchemyError

from productiq.database.pgvector import (
    PGVECTOR_EXTENSION_NAME,
    check_pgvector_extension,
    ensure_pgvector_extension,
    is_pgvector_extension_enabled,
    is_pgvector_python_available,
    require_pgvector_python_support,
)
from productiq.exceptions import DatabaseError, PgvectorExtensionError, ProductIQError


@pytest.fixture
def mock_engine() -> MagicMock:
    engine = MagicMock()
    connection = MagicMock()
    result = MagicMock()
    connection.execute.return_value = result
    engine.connect.return_value.__enter__.return_value = connection
    engine.connect.return_value.__exit__.return_value = None
    engine.begin.return_value.__enter__.return_value = connection
    engine.begin.return_value.__exit__.return_value = None
    return engine


def test_is_pgvector_python_available_when_package_installed() -> None:
    assert is_pgvector_python_available() is True


def test_require_pgvector_python_support_passes_when_installed() -> None:
    require_pgvector_python_support()


def test_require_pgvector_python_support_raises_when_package_missing() -> None:
    with patch(
        "productiq.database.pgvector.is_pgvector_python_available",
        return_value=False,
    ), pytest.raises(PgvectorExtensionError, match="Python package is not installed"):
        require_pgvector_python_support()


def test_is_pgvector_extension_enabled_returns_true_when_extension_present(
    mock_engine: MagicMock,
) -> None:
    connection = mock_engine.connect.return_value.__enter__.return_value
    connection.execute.return_value.scalar_one.return_value = True

    assert is_pgvector_extension_enabled(mock_engine) is True

    executed = connection.execute.call_args.args[0]
    assert executed.text.strip().startswith("SELECT EXISTS")
    assert connection.execute.call_args.args[1] == {
        "extension_name": PGVECTOR_EXTENSION_NAME,
    }


def test_is_pgvector_extension_enabled_returns_false_when_extension_missing(
    mock_engine: MagicMock,
) -> None:
    connection = mock_engine.connect.return_value.__enter__.return_value
    connection.execute.return_value.scalar_one.return_value = False

    assert is_pgvector_extension_enabled(mock_engine) is False


def test_check_pgvector_extension_raises_when_extension_missing(
    mock_engine: MagicMock,
) -> None:
    with patch(
        "productiq.database.pgvector.is_pgvector_extension_enabled",
        return_value=False,
    ), pytest.raises(PgvectorExtensionError, match="PostgreSQL pgvector extension"):
        check_pgvector_extension(mock_engine)


def test_check_pgvector_extension_passes_when_extension_enabled(
    mock_engine: MagicMock,
) -> None:
    with patch(
        "productiq.database.pgvector.is_pgvector_extension_enabled",
        return_value=True,
    ):
        check_pgvector_extension(mock_engine)


def test_is_pgvector_extension_enabled_raises_database_error_on_sqlalchemy_error(
    mock_engine: MagicMock,
) -> None:
    mock_engine.connect.side_effect = SQLAlchemyError("connection failed")

    with pytest.raises(DatabaseError, match="Failed to verify pgvector extension"):
        is_pgvector_extension_enabled(mock_engine)


def test_ensure_pgvector_extension_executes_create_extension(
    mock_engine: MagicMock,
) -> None:
    connection = mock_engine.begin.return_value.__enter__.return_value

    with patch(
        "productiq.database.pgvector.check_pgvector_extension",
    ) as mock_check:
        ensure_pgvector_extension(mock_engine)

    executed = connection.execute.call_args.args[0]
    assert executed.text == "CREATE EXTENSION IF NOT EXISTS vector"
    mock_check.assert_called_once_with(mock_engine)


def test_ensure_pgvector_extension_raises_pgvector_error_on_sqlalchemy_error(
    mock_engine: MagicMock,
) -> None:
    mock_engine.begin.side_effect = SQLAlchemyError("permission denied")

    with pytest.raises(PgvectorExtensionError, match="Failed to enable the PostgreSQL pgvector"):
        ensure_pgvector_extension(mock_engine)


def test_pgvector_extension_error_inherits_from_productiq_error() -> None:
    error = PgvectorExtensionError("missing")

    assert isinstance(error, ProductIQError)
    assert isinstance(error, DatabaseError)
