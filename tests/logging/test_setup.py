"""Tests for logging setup."""

import importlib
from io import StringIO

from productiq.config.settings import LogLevel, Settings
from productiq.logging.setup import (
    DATE_FORMAT,
    LOG_FORMAT,
    PRODUCTIQ_LOGGER_NAME,
    get_logger,
    setup_logging,
)

stdlib_logging = importlib.import_module("logging")


def test_get_logger_returns_named_logger() -> None:
    logger = get_logger("productiq.tests.sample")

    assert logger.name == "productiq.tests.sample"


def test_configured_log_level_is_respected() -> None:
    settings = Settings(_env_file=None, log_level=LogLevel.ERROR)

    setup_logging(settings)

    root_logger = stdlib_logging.getLogger(PRODUCTIQ_LOGGER_NAME)
    assert root_logger.level == stdlib_logging.ERROR


def test_repeated_setup_does_not_create_duplicate_handlers() -> None:
    settings = Settings(_env_file=None)

    setup_logging(settings)
    setup_logging(settings)

    root_logger = stdlib_logging.getLogger(PRODUCTIQ_LOGGER_NAME)
    assert len(root_logger.handlers) == 1


def test_logging_produces_expected_structure() -> None:
    settings = Settings(_env_file=None, log_level=LogLevel.INFO)
    setup_logging(settings)

    stream = StringIO()
    root_logger = stdlib_logging.getLogger(PRODUCTIQ_LOGGER_NAME)
    root_logger.handlers.clear()

    handler = stdlib_logging.StreamHandler(stream)
    handler.setFormatter(stdlib_logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
    root_logger.addHandler(handler)

    logger = get_logger("productiq.tests.format")
    logger.info("structured message")

    output = stream.getvalue()

    assert "INFO" in output
    assert "productiq.tests.format" in output
    assert "structured message" in output
    assert "|" in output
