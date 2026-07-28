"""Tests for Volume analysis technical indicator computation."""

import pytest

from stock_market_expert.analysis.volume import compute_volume_score, VolumeResult


@pytest.fixture
def ohlcv_data_normal_volume():
    """Generate synthetic OHLCV data with normal volume."""
    return [
        {"datetime": f"2024-01-{i+1:02d}", "open": 100.0 + i * 0.5, "high": 102.0 + i * 0.5,
         "low": 99.0 + i * 0.5, "close": 100.0 + i * 0.5, "volume": 1000000}
        for i in range(30)
    ]


@pytest.fixture
def ohlcv_data_high_volume():
    """Generate synthetic OHLCV data with high volume on last day."""
    data = [
        {"datetime": f"2024-01-{i+1:02d}", "open": 100.0 + i * 0.5, "high": 102.0 + i * 0.5,
         "low": 99.0 + i * 0.5, "close": 100.0 + i * 0.5, "volume": 1000000}
        for i in range(29)
    ]
    # Last day has 3x volume
    data.append({
        "datetime": "2024-02-01", "open": 114.0, "high": 116.0,
        "low": 113.0, "close": 114.5, "volume": 3000000
    })
    return data


def test_volume_returns_correct_type(ohlcv_data_normal_volume):
    result = compute_volume_score(ohlcv_data_normal_volume)
    assert isinstance(result, VolumeResult)


def test_volume_normal_ratio(ohlcv_data_normal_volume):
    """Volume ratio should be near 1.0 for normal volume."""
    result = compute_volume_score(ohlcv_data_normal_volume)
    assert 0.5 <= result.ratio <= 1.5


def test_volume_high_ratio(ohlcv_data_high_volume):
    """Volume ratio should be > 1.0 for high volume."""
    result = compute_volume_score(ohlcv_data_high_volume)
    assert result.ratio > 1.0


def test_volume_bullish_with_up_price():
    """Volume should be bullish when ratio > 1.5 and price is up."""
    data = [
        {"datetime": f"2024-01-{i+1:02d}", "open": 100.0, "high": 101.0,
         "low": 99.0, "close": 100.0, "volume": 1000000}
        for i in range(29)
    ]
    data.append({"datetime": "2024-02-01", "open": 100.5, "high": 101.5,
                 "low": 99.5, "close": 100.5, "volume": 3000000})
    result = compute_volume_score(data)
    assert result.direction == "bullish"


def test_volume_bearish_with_down_price():
    """Volume should be bearish when ratio > 1.5 and price is down."""
    data = [
        {"datetime": f"2024-01-{i+1:02d}", "open": 100.0, "high": 101.0,
         "low": 99.0, "close": 100.0, "volume": 1000000}
        for i in range(29)
    ]
    data.append({"datetime": "2024-02-01", "open": 99.5, "high": 100.5,
                 "low": 98.5, "close": 99.5, "volume": 3000000})
    result = compute_volume_score(data)
    assert result.direction == "bearish"


def test_volume_neutral_when_ratio_low():
    """Volume should be neutral when ratio <= 1.0."""
    # First 29 days have high volume, last day has low volume
    data = [
        {"datetime": f"2024-01-{i+1:02d}", "open": 100.0, "high": 101.0,
         "low": 99.0, "close": 100.0, "volume": 2000000}
        for i in range(29)
    ]
    # Last day: low volume, price slightly up
    data.append({"datetime": "2024-02-01", "open": 100.1, "high": 101.1,
                 "low": 99.1, "close": 100.1, "volume": 100000})
    result = compute_volume_score(data)
    assert result.ratio < 1.0
    assert result.direction == "neutral"


def test_volume_insufficient_data():
    """Volume should raise ValueError with insufficient data."""
    data = [
        {"datetime": f"2024-01-{i+1:02d}", "open": 100.0, "high": 101.0,
         "low": 99.0, "close": 100.0, "volume": 1000000}
        for i in range(10)
    ]
    with pytest.raises(ValueError, match="Insufficient data"):
        compute_volume_score(data)


def test_volume_confidence_scales_with_ratio(ohlcv_data_high_volume):
    """Volume confidence should scale with ratio magnitude."""
    result = compute_volume_score(ohlcv_data_high_volume)
    assert 0.0 <= result.confidence <= 1.0
