"""Unit tests for database health checks."""

from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import SQLAlchemyError

from productiq.database.health import check_database_health
from productiq.exceptions import DatabaseError


@pytest.fixture
def mock_engine() -> MagicMock:
    engine = MagicMock()
    connection = MagicMock()
    result = MagicMock()
    result.scalar_one.return_value = 1
    connection.execute.return_value = result
    engine.connect.return_value.__enter__.return_value = connection
    engine.connect.return_value.__exit__.return_value = None
    return engine


def test_check_database_health_executes_select_one(mock_engine: MagicMock) -> None:
    check_database_health(mock_engine)

    connection = mock_engine.connect.return_value.__enter__.return_value
    connection.execute.assert_called_once()
    executed = connection.execute.call_args.args[0]
    assert executed.text == "SELECT 1"


def test_check_database_health_raises_database_error_on_sqlalchemy_error(
    mock_engine: MagicMock,
) -> None:
    mock_engine.connect.side_effect = SQLAlchemyError("connection failed")

    with pytest.raises(DatabaseError, match="Database health check failed."):
        check_database_health(mock_engine)


def test_check_database_health_raises_database_error_on_unexpected_result(
    mock_engine: MagicMock,
) -> None:
    connection = mock_engine.connect.return_value.__enter__.return_value
    connection.execute.return_value.scalar_one.return_value = 0

    with pytest.raises(DatabaseError, match="unexpected result"):
        check_database_health(mock_engine)
