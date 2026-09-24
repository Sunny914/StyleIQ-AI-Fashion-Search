"""Unit tests for database session management."""

from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session, sessionmaker

from productiq.database.session import create_session_factory, session_scope


def test_create_session_factory_returns_sessionmaker() -> None:
    mock_engine = MagicMock()

    factory = create_session_factory(mock_engine)

    assert isinstance(factory, sessionmaker)


def test_session_scope_commits_and_closes_session() -> None:
    mock_session = MagicMock(spec=Session)
    mock_factory = MagicMock(spec=sessionmaker)
    mock_factory.return_value = mock_session

    with session_scope(mock_factory) as session:
        assert session is mock_session

    mock_session.commit.assert_called_once()
    mock_session.close.assert_called_once()
    mock_session.rollback.assert_not_called()


def test_session_scope_rolls_back_and_closes_on_error() -> None:
    mock_session = MagicMock(spec=Session)
    mock_factory = MagicMock(spec=sessionmaker)
    mock_factory.return_value = mock_session

    with pytest.raises(RuntimeError, match="failure"), session_scope(mock_factory):
        raise RuntimeError("failure")

    mock_session.rollback.assert_called_once()
    mock_session.close.assert_called_once()
    mock_session.commit.assert_not_called()
