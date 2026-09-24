"""Logging setup for ProductIQ."""

from __future__ import annotations

import logging

from productiq.config.settings import Settings, get_settings

LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
PRODUCTIQ_LOGGER_NAME = "productiq"

_configured = False


def setup_logging(settings: Settings | None = None) -> None:
    """Configure ProductIQ application logging once."""
    global _configured

    if _configured:
        return

    resolved_settings = settings or get_settings()

    logger = logging.getLogger(PRODUCTIQ_LOGGER_NAME)

    logger.setLevel(resolved_settings.log_level.value)
    logger.propagate = False

    if not logger.handlers:
        handler = logging.StreamHandler()

        formatter = logging.Formatter(
            fmt=LOG_FORMAT,
            datefmt=DATE_FORMAT,
        )

        handler.setFormatter(formatter)
        logger.addHandler(handler)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a logger for the given module name."""
    setup_logging()
    return logging.getLogger(name)


def reset_logging_configuration() -> None:
    """Reset logging configuration for testing."""
    global _configured

    _configured = False

    logger = logging.getLogger(PRODUCTIQ_LOGGER_NAME)
    logger.handlers.clear()
    logger.setLevel(logging.NOTSET)
    logger.propagate = True