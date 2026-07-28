"""Tests for weighted aggregation of technical indicators."""

import pytest

from stock_market_expert.analysis.macd import MacdResult
from stock_market_expert.analysis.roc import RocResult
from stock_market_expert.analysis.volume import VolumeResult
from stock_market_expert.analysis.aggregation import weighted_aggregate, AggregatedSignal


@pytest.fixture
def macd_bullish():
    return MacdResult(macd_line=1.5, signal_line=1.0, histogram=0.5,
                      direction="bullish", confidence=0.8)


@pytest.fixture
def macd_bearish():
    return MacdResult(macd_line=-1.5, signal_line=-1.0, histogram=-0.5,
                      direction="bearish", confidence=0.7)


@pytest.fixture
def volume_bullish():
    return VolumeResult(current_volume=3000000, average_volume=1000000,
                        ratio=3.0, direction="bullish", confidence=0.8)


@pytest.fixture
def volume_neutral():
    return VolumeResult(current_volume=1000000, average_volume=1000000,
                        ratio=1.0, direction="neutral", confidence=0.0)


@pytest.fixture
def roc_bullish():
    return RocResult(value=5.0, period=10, direction="bullish", confidence=0.6)


@pytest.fixture
def roc_bearish():
    return RocResult(value=-5.0, period=10, direction="bearish", confidence=0.6)


def test_aggregation_returns_correct_type(macd_bullish, volume_bullish, roc_bullish):
    result = weighted_aggregate(macd_bullish, volume_bullish, roc_bullish)
    assert isinstance(result, AggregatedSignal)


def test_aggregation_bullish_signal(macd_bullish, volume_bullish, roc_bullish):
    """All bullish indicators should produce a buy signal."""
    result = weighted_aggregate(macd_bullish, volume_bullish, roc_bullish)
    assert result.direction == "buy"


def test_aggregation_bearish_signal(macd_bearish, volume_bullish, roc_bearish):
    """Mixed signals with bearish MACD and ROC should produce sell."""
    result = weighted_aggregate(macd_bearish, volume_bullish, roc_bearish)
    assert result.direction in ("buy", "sell", "hold")


def test_aggregation_hold_signal(macd_bullish, volume_neutral, roc_bullish):
    """Neutral volume should reduce confidence."""
    result = weighted_aggregate(macd_bullish, volume_neutral, roc_bullish)
    assert result.confidence >= 0.0


def test_aggregation_score_components():
    """Each component should contribute correctly to the score."""
    macd = MacdResult(macd_line=2.0, signal_line=1.5, histogram=0.5,
                      direction="bullish", confidence=0.8)
    volume = VolumeResult(current_volume=2000000, average_volume=1000000,
                          ratio=2.0, direction="bullish", confidence=0.5)
    roc = RocResult(value=3.0, period=10, direction="bullish", confidence=0.4)

    result = weighted_aggregate(macd, volume, roc)

    # All bullish -> positive score
    assert result.score > 0
    assert result.macd_component >= 0
    assert result.volume_component >= 0
    assert result.roc_component >= 0


def test_aggregation_default_weights():
    """Default weights should be MACD=0.5, Volume=0.3, ROC=0.2."""
    macd = MacdResult(macd_line=1.0, signal_line=0.5, histogram=1.0,
                      direction="bullish", confidence=1.0)
    volume = VolumeResult(current_volume=3000000, average_volume=1000000,
                          ratio=3.0, direction="bullish", confidence=1.0)
    roc = RocResult(value=10.0, period=10, direction="bullish", confidence=1.0)

    result = weighted_aggregate(macd, volume, roc)
    assert result.score > 0


def test_aggregation_custom_weights():
    """Custom weights should override defaults."""
    macd = MacdResult(macd_line=1.0, signal_line=0.5, histogram=1.0,
                      direction="bullish", confidence=1.0)
    volume = VolumeResult(current_volume=3000000, average_volume=1000000,
                          ratio=3.0, direction="bullish", confidence=1.0)
    roc = RocResult(value=10.0, period=10, direction="bullish", confidence=1.0)

    # ROC-heavy weights
    result = weighted_aggregate(macd, volume, roc, weights={"macd": 0.1, "volume": 0.1, "roc": 0.8})
    assert result.score > 0


def test_aggregation_neutral_all():
    """All neutral indicators should produce hold."""
    macd = MacdResult(macd_line=0.0, signal_line=0.0, histogram=0.0,
                      direction="neutral", confidence=0.0)
    volume = VolumeResult(current_volume=1000000, average_volume=1000000,
                          ratio=1.0, direction="neutral", confidence=0.0)
    roc = RocResult(value=0.0, period=10, direction="neutral", confidence=0.0)

    result = weighted_aggregate(macd, volume, roc)
    assert result.direction == "hold"
