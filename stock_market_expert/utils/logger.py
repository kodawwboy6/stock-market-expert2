"""Common logging utilities for the stock market expert system.

Provides a consistent logger factory that configures structured JSON
logging with timestamp, level, step, action, and details.
"""

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def get_logger(
    name: str = "stock_market_expert",
    log_dir: Optional[Path] = None,
    level: str = "INFO",
    retention_days: int = 30,
) -> logging.Logger:
    """Get a configured logger with structured JSON file handler.

    Args:
        name: Logger name (used for module-level separation).
        log_dir: Directory for log files. Defaults to logs/ in cwd.
        level: Logging level string (DEBUG, INFO, WARNING, ERROR).
        retention_days: Number of days to retain log files.

    Returns:
        Configured logging.Logger instance.
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Avoid adding duplicate handlers
    if logger.handlers:
        return logger

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, level.upper(), logging.INFO))
    console_format = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)

    # JSON file handler
    log_dir = log_dir or Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    file_handler = _get_json_file_handler(log_dir, retention_days)
    logger.addHandler(file_handler)

    return logger


def _get_json_file_handler(
    log_dir: Path, retention_days: int
) -> logging.Handler:
    """Create a file handler that writes structured JSON log entries.

    Args:
        log_dir: Directory for log files.
        retention_days: Number of days to retain log files.

    Returns:
        Configured logging.Handler instance.
    """

    class JsonFileHandler(logging.Handler):
        """Handler that writes log records as structured JSON."""

        def emit(self, record: logging.LogRecord) -> None:
            """Emit a log record as a JSON line."""
            log_entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
            }
            if hasattr(record, "step"):
                log_entry["step"] = record.step
            if hasattr(record, "action"):
                log_entry["action"] = record.action
            if record.exc_info and record.exc_info[0] is not None:
                log_entry["exception"] = self.format(record)

            log_file = log_dir / f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.log"
            with open(log_file, "a") as f:
                f.write(json.dumps(log_entry) + "\n")

    handler = JsonFileHandler()
    # Clean up old log files
    _cleanup_old_logs(log_dir, retention_days)
    return handler


def _cleanup_old_logs(log_dir: Path, retention_days: int) -> None:
    """Remove log files older than retention_days.

    Args:
        log_dir: Directory containing log files.
        retention_days: Number of days to retain.
    """
    from datetime import timedelta

    cutoff = datetime.now(timezone.utc).date() - timedelta(days=retention_days)
    for log_file in log_dir.glob("*.log"):
        try:
            file_date = datetime.strptime(
                log_file.stem, "%Y-%m-%d"
            ).date()
            if file_date < cutoff:
                log_file.unlink()
        except ValueError:
            # Skip files that don't match the date format
            pass
