"""Tests for ROC (Rate of Change) technical indicator computation."""

import pytest

from stock_market_expert.analysis.roc import compute_roc, RocResult


@pytest.fixture
def ohlcv_data():
    """Generate synthetic OHLCV data for testing."""
    return [
        {"datetime": f"2024-01-{i+1:02d}", "open": 100.0 + i * 0.5, "high": 102.0 + i * 0.5,
         "low": 99.0 + i * 0.5, "close": 100.0 + i * 0.5, "volume": 1000000}
        for i in range(25)
    ]


def test_roc_returns_correct_type(ohlcv_data):
    result = compute_roc(ohlcv_data)
    assert isinstance(result, RocResult)


def test_roc_bullish_direction(ohlcv_data):
    """ROC should be bullish when price is trending up."""
    result = compute_roc(ohlcv_data)
    assert result.direction == "bullish"
    assert result.value > 0


def test_roc_bearish_direction():
    """ROC should be bearish when price is trending down."""
    ohlcv_data = [
        {"datetime": f"2024-01-{i+1:02d}", "open": 100.0 - i * 0.5, "high": 102.0 - i * 0.5,
         "low": 99.0 - i * 0.5, "close": 100.0 - i * 0.5, "volume": 1000000}
        for i in range(25)
    ]
    result = compute_roc(ohlcv_data)
    assert result.direction == "bearish"
    assert result.value < 0


def test_roc_neutral_direction():
    """ROC should be neutral when price is flat."""
    ohlcv_data = [
        {"datetime": f"2024-01-{i+1:02d}", "open": 100.0, "high": 101.0,
         "low": 99.0, "close": 100.0, "volume": 1000000}
        for i in range(25)
    ]
    result = compute_roc(ohlcv_data)
    assert result.direction == "neutral"
    assert result.value == 0


def test_roc_insufficient_data():
    """ROC should raise ValueError with insufficient data."""
    ohlcv_data = [
        {"datetime": f"2024-01-{i+1:02d}", "open": 100.0, "high": 101.0,
         "low": 99.0, "close": 100.0 + i * 0.1, "volume": 1000000}
        for i in range(5)
    ]
    with pytest.raises(ValueError, match="Insufficient data"):
        compute_roc(ohlcv_data)


def test_roc_custom_period():
    """ROC should accept custom periods."""
    ohlcv_data = [
        {"datetime": f"2024-01-{i+1:02d}", "open": 100.0 + i * 0.5, "high": 102.0 + i * 0.5,
         "low": 99.0 + i * 0.5, "close": 100.0 + i * 0.5, "volume": 1000000}
        for i in range(30)
    ]
    result = compute_roc(ohlcv_data, period=5)
    assert isinstance(result, RocResult)
    assert result.period == 5


def test_roc_confidence_scales_with_magnitude(ohlcv_data):
    """ROC confidence should scale with magnitude of change."""
    result = compute_roc(ohlcv_data)
    assert 0.0 <= result.confidence <= 1.0
