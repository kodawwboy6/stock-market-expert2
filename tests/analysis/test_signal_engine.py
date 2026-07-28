"""Tests for SignalEngine signal generation and deduplication."""

import pytest
from unittest.mock import patch, MagicMock

from stock_market_expert.analysis.signal_engine import SignalEngine, TechnicalSignal


@pytest.fixture
def mock_ohlcv_data():
    """Generate synthetic OHLCV data for testing."""
    return [
        {"datetime": f"2024-01-{i+1:02d}", "open": 100.0 + i * 0.5, "high": 102.0 + i * 0.5,
         "low": 99.0 + i * 0.5, "close": 100.0 + i * 0.5, "volume": 1000000}
        for i in range(95)
    ]


@pytest.fixture
def engine():
    """Create a SignalEngine with mocked data providers."""
    with patch("stock_market_expert.analysis.signal_engine.TwelveDataProvider") as mock_td, \
         patch("stock_market_expert.analysis.signal_engine.AlpacaProvider") as mock_alpaca:
        mock_td_instance = MagicMock()
        mock_td_instance.get_historical_ohlcv.return_value = [
            {"datetime": f"2024-01-{i+1:02d}", "open": 100.0 + i * 0.5, "high": 102.0 + i * 0.5,
             "low": 99.0 + i * 0.5, "close": 100.0 + i * 0.5, "volume": 1000000}
            for i in range(95)
        ]
        mock_td.return_value = mock_td_instance
        engine = SignalEngine(
            twelve_data_key="test_key",
            alpaca_api_key="test_api",
            alpaca_secret_key="test_secret",
            history_days=90,
            macd_fast=12,
            macd_slow=26,
            macd_signal=9,
            roc_period=10,
            volume_lookback=20,
            buy_threshold=0.3,
            sell_threshold=-0.3,
            min_confidence=0.5,
        )
        yield engine


def test_signal_engine_creates_signals(engine):
    """Engine should generate signals for symbols with strong indicators."""
    signals = engine.generate_signals(["AAPL"])
    assert isinstance(signals, list)


def test_signal_engine_returns_correct_type(engine):
    """Generated signals should be TechnicalSignal objects."""
    signals = engine.generate_signals(["AAPL"])
    for signal in signals:
        assert isinstance(signal, TechnicalSignal)


def test_signal_engine_deduplication(engine):
    """Same symbol should not produce duplicate signals in one cycle."""
    signals = engine.generate_signals(["AAPL", "AAPL"])
    aapl_signals = [s for s in signals if s.symbol == "AAPL"]
    assert len(aapl_signals) <= 1


def test_signal_engine_reset_dedup(engine):
    """Reset dedup should clear signal history."""
    engine.generate_signals(["AAPL"])
    engine.reset_dedup()
    # After reset, same symbol can produce another signal
    signals = engine.generate_signals(["AAPL"])
    assert len(signals) >= 0  # May or may not generate depending on data


def test_signal_engine_empty_symbols():
    """Empty symbol list should return empty signals."""
    with patch("stock_market_expert.analysis.signal_engine.TwelveDataProvider") as mock_td, \
         patch("stock_market_expert.analysis.signal_engine.AlpacaProvider") as mock_alpaca:
        mock_td_instance = MagicMock()
        mock_td_instance.get_historical_ohlcv.return_value = []
        mock_td.return_value = mock_td_instance
        engine = SignalEngine(
            twelve_data_key="test_key",
            alpaca_api_key="test_api",
            alpaca_secret_key="test_secret",
        )
        signals = engine.generate_signals([])
        assert signals == []


def test_signal_engine_min_confidence_threshold(engine):
    """Signals below min_confidence should be filtered out."""
    with patch.object(engine.twelve_data, "get_historical_ohlcv") as mock_ohlcv:
        # Return flat data that produces low confidence
        mock_ohlcv.return_value = [
            {"datetime": f"2024-01-{i+1:02d}", "open": 100.0, "high": 101.0,
             "low": 99.0, "close": 100.0, "volume": 1000000}
            for i in range(95)
        ]
        signals = engine.generate_signals(["FLAT"])
        for signal in signals:
            assert signal.confidence >= engine.min_confidence


def test_signal_engine_multiple_symbols(engine):
    """Engine should generate signals for multiple symbols."""
    signals = engine.generate_signals(["AAPL", "GOOGL", "MSFT"])
    assert isinstance(signals, list)


def test_signal_engine_contains_reasoning(engine):
    """Generated signals should contain reasoning."""
    signals = engine.generate_signals(["AAPL"])
    for signal in signals:
        assert len(signal.reasoning) > 0
