"""Tests for the utils/logger module."""

import logging
from pathlib import Path

from stock_market_expert.utils.logger import get_logger


class TestGetLogger:
    """Tests for the get_logger function."""

    def test_returns_logger(self):
        """get_logger should return a logging.Logger instance."""
        logger = get_logger("test_returns_logger_unique")
        assert isinstance(logger, logging.Logger)

    def test_logger_name(self):
        """Logger should use the provided name."""
        logger = get_logger("test_logger_name_unique")
        assert logger.name == "test_logger_name_unique"

    def test_creates_log_dir(self, tmp_path):
        """get_logger should create the log directory if it doesn't exist."""
        log_dir = tmp_path / "logs"
        assert not log_dir.exists()

        logger = get_logger("test_creates_log_dir_unique", log_dir=log_dir)

        assert log_dir.exists()

    def test_log_level(self):
        """Logger should respect the configured log level."""
        logger = get_logger("test_log_level_unique", level="DEBUG")
        assert logger.level == logging.DEBUG

    def test_log_level_default(self):
        """Default log level should be INFO."""
        logger = get_logger("test_log_level_default_unique")
        assert logger.level == logging.INFO

    def test_multiple_calls_return_same_logger(self):
        """Multiple calls with same name should return the same logger."""
        logger1 = get_logger("test_singleton_unique")
        logger2 = get_logger("test_singleton_unique")
        assert logger1 is logger2
