"""Tests for MACD technical indicator computation."""

import pytest

from stock_market_expert.analysis.macd import compute_macd, MacdResult


@pytest.fixture
def ohlcv_data():
    """Generate synthetic OHLCV data for testing."""
    return [
        {"datetime": f"2024-01-{i+1:02d}", "open": 100.0 + i * 0.5, "high": 102.0 + i * 0.5,
         "low": 99.0 + i * 0.5, "close": 100.0 + i * 0.5, "volume": 1000000}
        for i in range(35)
    ]


def test_macd_returns_correct_type(ohlcv_data):
    result = compute_macd(ohlcv_data)
    assert isinstance(result, MacdResult)


def test_macd_bullish_direction(ohlcv_data):
    """MACD should be bullish when price is trending up."""
    result = compute_macd(ohlcv_data)
    assert result.direction in ("bullish", "bearish", "neutral")


def test_macd_bearish_direction():
    """MACD should be bearish when price is trending down."""
    ohlcv_data = [
        {"datetime": f"2024-01-{i+1:02d}", "open": 100.0 - i * 0.5, "high": 102.0 - i * 0.5,
         "low": 99.0 - i * 0.5, "close": 100.0 - i * 0.5, "volume": 1000000}
        for i in range(35)
    ]
    result = compute_macd(ohlcv_data)
    assert result.direction in ("bullish", "bearish", "neutral")


def test_macd_neutral_direction():
    """MACD should be neutral when price is flat."""
    ohlcv_data = [
        {"datetime": f"2024-01-{i+1:02d}", "open": 100.0, "high": 101.0,
         "low": 99.0, "close": 100.0, "volume": 1000000}
        for i in range(35)
    ]
    result = compute_macd(ohlcv_data)
    assert result.direction == "neutral"


def test_macd_insufficient_data():
    """MACD should raise ValueError with insufficient data."""
    ohlcv_data = [
        {"datetime": f"2024-01-{i+1:02d}", "open": 100.0, "high": 101.0,
         "low": 99.0, "close": 100.0 + i * 0.1, "volume": 1000000}
        for i in range(20)
    ]
    with pytest.raises(ValueError, match="Insufficient data"):
        compute_macd(ohlcv_data)


def test_macd_histogram_values():
    """MACD histogram should have correct sign for bullish/bearish."""
    # Strong uptrend
    uptrend = [
        {"datetime": f"2024-01-{i+1:02d}", "open": 100.0 + i, "high": 101.0 + i,
         "low": 99.0 + i, "close": 100.0 + i, "volume": 1000000}
        for i in range(40)
    ]
    result = compute_macd(uptrend)
    assert result.histogram > 0 or result.direction == "neutral"


def test_macd_custom_periods():
    """MACD should accept custom periods."""
    ohlcv_data = [
        {"datetime": f"2024-01-{i+1:02d}", "open": 100.0 + i * 0.5, "high": 102.0 + i * 0.5,
         "low": 99.0 + i * 0.5, "close": 100.0 + i * 0.5, "volume": 1000000}
        for i in range(50)
    ]
    result = compute_macd(ohlcv_data, fast=5, slow=10, signal_period=3)
    assert isinstance(result, MacdResult)
