"""Error handler module for the stock market expert system.

Provides centralized error logging, retry logic with exponential backoff,
and structured logging for observability.
"""

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class ErrorHandler:
    """Centralized error handler for the stock market expert system.

    Logs errors to structured JSON files and provides step tracking.
    """

    def __init__(self, log_dir: Optional[Path] = None):
        """Initialize the error handler.

        Args:
            log_dir: Directory to store log files. Defaults to logs/ in the project root.
        """
        self.log_dir = log_dir or Path("logs")
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def log_error(
        self,
        error: Exception,
        context: str,
        step: str,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        """Log an error to a structured JSON file.

        Args:
            error: The exception to log.
            context: The context in which the error occurred.
            step: The execution step (e.g., "step1", "step2", "step3").
            details: Additional details about the error.
        """
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": "ERROR",
            "context": context,
            "step": step,
            "message": str(error),
            "error_type": type(error).__name__,
        }
        if details:
            log_entry["details"] = details

        # Write to log file
        log_file = self.log_dir / f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.log"
        with open(log_file, "a") as f:
            f.write(json.dumps(log_entry) + "\n")

        # Also log to stderr
        logger.error(f"[{step}] {context}: {error}")

    def log_step_start(self, step: str) -> None:
        """Log the start of a step.

        Args:
            step: The execution step (e.g., "step1", "step2", "step3").
        """
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": "INFO",
            "step": step,
            "action": "step_start",
        }

        log_file = self.log_dir / f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.log"
        with open(log_file, "a") as f:
            f.write(json.dumps(log_entry) + "\n")

        logger.info(f"Starting {step}")

    def log_step_complete(self, step: str) -> None:
        """Log the completion of a step.

        Args:
            step: The execution step (e.g., "step1", "step2", "step3").
        """
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": "INFO",
            "step": step,
            "action": "step_complete",
        }

        log_file = self.log_dir / f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.log"
        with open(log_file, "a") as f:
            f.write(json.dumps(log_entry) + "\n")

        logger.info(f"Completed {step}")


# Module-level convenience functions
DEFAULT_HANDLER = ErrorHandler()


def log_error(
    error: Exception,
    context: str,
    step: str,
    details: Optional[dict[str, Any]] = None,
) -> None:
    """Module-level convenience function for logging errors.

    Args:
        error: The exception to log.
        context: The context in which the error occurred.
        step: The execution step (e.g., "step1", "step2", "step3").
        details: Additional details about the error.
    """
    DEFAULT_HANDLER.log_error(error, context, step, details)


def log_step_start(step: str) -> None:
    """Module-level convenience function for logging step start.

    Args:
        step: The execution step (e.g., "step1", "step2", "step3").
    """
    DEFAULT_HANDLER.log_step_start(step)


def log_step_complete(step: str) -> None:
    """Module-level convenience function for logging step completion.

    Args:
        step: The execution step (e.g., "step1", "step2", "step3").
    """
    DEFAULT_HANDLER.log_step_complete(step)


def retry_with_backoff(
    func: Callable,
    max_retries: int = 3,
    delay_factor: float = 1.0,
    max_delay: float = 60.0,
    fallback_date: Optional[str] = None,
    fallback_data: Optional[Any] = None,
) -> Any:
    """Retry a function with exponential backoff.

    If all retries fail and a fallback_date is provided, use the fallback
    data instead. This is used for Step 1 (news analysis) where we want
    to continue with yesterday's data if today's data is unavailable.

    Args:
        func: The function to retry.
        max_retries: Maximum number of retries.
        delay_factor: Base delay factor for exponential backoff.
        max_delay: Maximum delay between retries.
        fallback_date: Date to use for fallback data (e.g., "2024-01-15").
        fallback_data: Data to return if all retries fail.

    Returns:
        The result of the function, or fallback_data if all retries fail.

    Raises:
        The last exception if all retries fail and no fallback_data is provided.
    """
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            return func()
        except Exception as e:
            last_exception = e
            if attempt < max_retries:
                delay = min(delay_factor * (2 ** attempt), max_delay)
                logger.warning(
                    f"Attempt {attempt + 1}/{max_retries + 1} failed: {e}. "
                    f"Retrying in {delay:.1f}s..."
                )
                time.sleep(delay)
            else:
                # All retries failed
                if fallback_data is not None:
                    logger.info(
                        f"All {max_retries} retries failed. "
                        f"Using fallback data (date: {fallback_date})."
                    )
                    return fallback_data
                logger.error(f"All {max_retries} retries failed. Raising exception.")
                raise

    # Should not reach here, but just in case
    if fallback_data is not None:
        return fallback_data
    raise last_exception
