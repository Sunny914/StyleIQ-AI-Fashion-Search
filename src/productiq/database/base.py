"""SQLAlchemy declarative base for ProductIQ database models."""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for ProductIQ ORM models."""


__all__ = ["Base"]
