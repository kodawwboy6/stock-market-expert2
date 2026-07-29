"""Tests for retry helper functions."""

import asyncio
import time

import pytest

from stock_market_expert.errors.handler import (
    DeadlineExceededError,
    async_retry_with_backoff,
    retry_with_backoff,
)


# --- sync retry_with_backoff ---


def test_retry_with_backoff_succeeds_first_try():
    """retry_with_backoff should return immediately on success."""
    call_count = 0

    def _fn():
        nonlocal call_count
        call_count += 1
        return 42

    result = retry_with_backoff(_fn, max_retries=3)
    assert result == 42
    assert call_count == 1


def test_retry_with_backoff_fallback_data():
    """retry_with_backoff should return fallback_data when all retries fail."""
    call_count = 0

    def _fn():
        nonlocal call_count
        call_count += 1
        raise RuntimeError("fail")

    result = retry_with_backoff(
        _fn, max_retries=2, fallback_data="fallback", fallback_date="2024-01-01"
    )
    assert result == "fallback"
    assert call_count == 3  # initial + 2 retries


def test_retry_with_backoff_deadline_expires():
    """retry_with_backoff should raise DeadlineExceededError when deadline expires."""
    call_count = 0
    past_deadline = time.time() - 1  # already expired

    def _fn():
        nonlocal call_count
        call_count += 1
        raise RuntimeError("fail")

    with pytest.raises(DeadlineExceededError):
        retry_with_backoff(_fn, max_retries=3, deadline=past_deadline)

    assert call_count == 1  # only the first call, deadline checked before retry


def test_retry_with_backoff_deadline_no_raise_on_first_success():
    """retry_with_backoff should not raise even if deadline is past, if the first call succeeds."""
    future_deadline = time.time() + 600

    def _fn():
        return "ok"

    result = retry_with_backoff(_fn, max_retries=3, deadline=future_deadline)
    assert result == "ok"


def test_retry_with_backoff_deadline_before_retry():
    """retry_with_backoff should raise DeadlineExceededError when deadline expires during retry loop."""
    call_count = 0
    deadline = time.time() + 0.3  # will expire during the first retry wait

    def _fn():
        nonlocal call_count
        call_count += 1
        raise RuntimeError("fail")

    with pytest.raises(DeadlineExceededError):
        retry_with_backoff(
            _fn, max_retries=3, delay_factor=0.5, deadline=deadline
        )

    # deadline (0.3s) expires before first retry delay (0.5s), so only 1 retry
    assert call_count == 2  # initial + 1 retry


# --- async async_retry_with_backoff ---


@pytest.mark.asyncio
async def test_async_retry_with_backoff_succeeds_first_try():
    """async_retry_with_backoff should return immediately on success."""
    call_count = 0

    async def _fn():
        nonlocal call_count
        call_count += 1
        return 42

    result = await async_retry_with_backoff(_fn, max_retries=3)
    assert result == 42
    assert call_count == 1


@pytest.mark.asyncio
async def test_async_retry_with_backoff_deadline_expires():
    """async_retry_with_backoff should raise DeadlineExceededError when deadline expires."""
    call_count = 0
    past_deadline = time.time() - 1

    async def _fn():
        nonlocal call_count
        call_count += 1
        raise RuntimeError("fail")

    with pytest.raises(DeadlineExceededError):
        await async_retry_with_backoff(_fn, max_retries=3, deadline=past_deadline)

    assert call_count == 1  # only the first call


@pytest.mark.asyncio
async def test_async_retry_with_backoff_deadline_before_retry():
    """async_retry_with_backoff should raise when deadline expires during retry."""
    call_count = 0
    deadline = time.time() + 0.3  # will expire during the first retry wait

    async def _fn():
        nonlocal call_count
        call_count += 1
        raise RuntimeError("fail")

    with pytest.raises(DeadlineExceededError):
        await async_retry_with_backoff(
            _fn, max_retries=3, delay_factor=0.5, deadline=deadline
        )

    # deadline (0.3s) expires before first retry delay (0.5s), so only 1 retry
    assert call_count == 2  # initial + 1 retry


# --- DeadlineExceededError ---


def test_deadline_exceeded_error_has_deadline():
    """DeadlineExceededError should store the deadline."""
    deadline = 1234567890.0
    err = DeadlineExceededError(deadline)
    assert err.deadline == deadline


def test_deadline_exceeded_error_message():
    """DeadlineExceededError message should include the deadline time."""
    deadline = 1234567890.0
    err = DeadlineExceededError(deadline)
    assert "Deadline exceeded" in str(err)
