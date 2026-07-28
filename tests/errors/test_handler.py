"""Tests for the error handler module."""

import json
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from stock_market_expert.errors.handler import (
    ErrorHandler,
    retry_with_backoff,
    log_error,
    log_step_start,
    log_step_complete,
)


class TestRetryWithBackoff:
    """Tests for the retry_with_backoff function."""

    def test_succeeds_on_first_try(self):
        """If the function succeeds on the first try, return the result."""
        mock_func = MagicMock(return_value="success")

        result = retry_with_backoff(mock_func, max_retries=3)

        assert result == "success"
        assert mock_func.call_count == 1

    def test_retries_on_failure_then_succeeds(self):
        """If the function fails twice then succeeds, retry should return the result."""
        call_count = 0

        def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Temporary failure")
            return "recovered"

        result = retry_with_backoff(flaky_func, max_retries=3)

        assert result == "recovered"
        assert call_count == 3

    def test_raises_after_max_retries(self):
        """If all retries fail, raise the last exception."""
        def always_fails():
            raise ConnectionError("Connection refused")

        with pytest.raises(ConnectionError, match="Connection refused"):
            retry_with_backoff(always_fails, max_retries=3)

    def test_uses_exponential_backoff(self):
        """Verify that delays increase exponentially."""
        delays = []

        def slow_func():
            delays.append(time.time())
            raise ConnectionError("Timeout")

        with pytest.raises(ConnectionError):
            retry_with_backoff(slow_func, max_retries=3, delay_factor=0.1, max_delay=1.0)

        # Check that delays increase (second delay > first delay)
        assert delays[1] - delays[0] < delays[2] - delays[1]

    def test_fallback_date_used_when_all_retries_fail(self):
        """If all retries fail, use the fallback date to get data."""
        fallback_data = [{"symbol": "AAPL", "headline": "Fallback news"}]

        def always_fails():
            raise ConnectionError("Timeout")

        result = retry_with_backoff(
            always_fails,
            max_retries=3,
            fallback_date="2024-01-15",
            fallback_data=fallback_data,
        )

        assert result == fallback_data


class TestErrorHandler:
    """Tests for the ErrorHandler class."""

    def test_log_error_creates_log_file(self, tmp_path):
        """Logging an error should create a log file."""
        handler = ErrorHandler(log_dir=tmp_path)

        handler.log_error(ValueError("Test error"), context="test", step="step1")

        log_files = list(tmp_path.glob("*.log"))
        assert len(log_files) == 1

    def test_log_error_writes_structured_json(self, tmp_path):
        """Error logs should be structured JSON."""
        handler = ErrorHandler(log_dir=tmp_path)

        handler.log_error(ValueError("Test error"), context="test", step="step1")

        log_files = list(tmp_path.glob("*.log"))
        with open(log_files[0]) as f:
            log_entry = json.loads(f.read())

        assert log_entry["level"] == "ERROR"
        assert log_entry["context"] == "test"
        assert log_entry["step"] == "step1"
        assert "message" in log_entry
        assert "timestamp" in log_entry

    def test_log_step_start_records_step(self, tmp_path):
        """Logging a step start should record it."""
        handler = ErrorHandler(log_dir=tmp_path)

        handler.log_step_start("step1")

        log_files = list(tmp_path.glob("*.log"))
        with open(log_files[0]) as f:
            log_entry = json.loads(f.read())

        assert log_entry["level"] == "INFO"
        assert log_entry["step"] == "step1"
        assert log_entry["action"] == "step_start"

    def test_log_step_complete_records_step(self, tmp_path):
        """Logging a step complete should record it."""
        handler = ErrorHandler(log_dir=tmp_path)

        handler.log_step_complete("step1")

        log_files = list(tmp_path.glob("*.log"))
        with open(log_files[0]) as f:
            log_entry = json.loads(f.read())

        assert log_entry["level"] == "INFO"
        assert log_entry["step"] == "step1"
        assert log_entry["action"] == "step_complete"


class TestLogErrorFunction:
    """Tests for the module-level log_error function."""

    def test_log_error_uses_default_handler(self, tmp_path):
        """The module-level log_error function should use a default handler."""
        with patch("stock_market_expert.errors.handler.DEFAULT_HANDLER") as mock_handler:
            mock_handler.log_error = MagicMock()

            log_error(ValueError("Test error"), context="test", step="step1")

            mock_handler.log_error.assert_called_once()
