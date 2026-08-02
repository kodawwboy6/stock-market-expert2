"""Tests for the TwelveDataProvider module.

Verifies response handling against the official Twelve Data API schema
documented in docs/adr/0005-external-api-documentation.md.
"""

from unittest.mock import MagicMock, patch

import pytest

from stock_market_expert.data.twelve_data_provider import TwelveDataProvider


class TestTwelveDataProviderNormalizeOhlcv:
    """Tests for _normalize_ohlcv with verified API response structure."""

    def test_normalizes_string_values_to_numeric_types(self):
        """_normalize_ohlcv must parse string fields to float/int per API docs."""
        raw = [
            {
                "datetime": "2024-01-15",
                "open": "187.14999",
                "high": "189.50000",
                "low": "186.20000",
                "close": "188.50000",
                "volume": "82488700",
            }
        ]
        provider = TwelveDataProvider(api_key="test_key")
        result = provider._normalize_ohlcv(raw)

        assert len(result) == 1
        assert result[0]["datetime"] == "2024-01-15"
        assert result[0]["open"] == 187.14999
        assert result[0]["high"] == 189.5
        assert result[0]["low"] == 186.2
        assert result[0]["close"] == 188.5
        assert result[0]["volume"] == 82488700
        assert isinstance(result[0]["open"], float)
        assert isinstance(result[0]["close"], float)
        assert isinstance(result[0]["volume"], int)

    def test_handles_missing_values_with_defaults(self):
        """_normalize_ohlcv should use safe defaults for missing fields."""
        raw = [{"datetime": "2024-01-15"}]
        provider = TwelveDataProvider(api_key="test_key")
        result = provider._normalize_ohlcv(raw)

        assert result[0]["open"] == 0.0
        assert result[0]["high"] == 0.0
        assert result[0]["low"] == 0.0
        assert result[0]["close"] == 0.0
        assert result[0]["volume"] == 0

    def test_handles_empty_list(self):
        """_normalize_ohlcv should return an empty list for empty input."""
        provider = TwelveDataProvider(api_key="test_key")
        result = provider._normalize_ohlcv([])
        assert result == []


class TestTwelveDataGetQuotes:
    """Tests for get_quotes against verified /price endpoint schema.

    Per official API docs (verified live):
    - /price returns only {price: string}
    - It does NOT return bid, ask, or volume.
    """

    def test_get_quotes_returns_only_price_field(self):
        """get_quotes should only read `price` from /price response."""
        # Verified live: /price returns only {"price": "309.029999"}
        mock_response = {"price": "309.029999"}

        with patch("httpx.get") as mock_get:
            mock_get.return_value = MagicMock(status_code=200, json=MagicMock(return_value=mock_response))

            provider = TwelveDataProvider(api_key="test_key")
            result = provider.get_quotes(["AAPL"])

            assert len(result) == 1
            assert result[0]["symbol"] == "AAPL"
            assert result[0]["last_price"] == 309.029999
            # Should NOT contain bid, ask, volume keys
            assert "bid" not in result[0]
            assert "ask" not in result[0]
            assert "volume" not in result[0]

    def test_get_quotes_handles_api_error(self):
        """get_quotes should include error info when API call fails."""
        with patch("httpx.get") as mock_get:
            mock_get.side_effect = Exception("Connection refused")

            provider = TwelveDataProvider(api_key="test_key")
            result = provider.get_quotes(["AAPL"])

            assert len(result) == 1
            assert result[0]["symbol"] == "AAPL"
            assert result[0]["last_price"] == 0.0
            assert "error" in result[0]
            assert "Connection refused" in result[0]["error"]

    def test_get_quotes_handles_multiple_symbols(self):
        """get_quotes should process all symbols."""
        with patch("httpx.get") as mock_get:
            mock_get.return_value = MagicMock(status_code=200, json=MagicMock(return_value={"price": "150.00"}))

            provider = TwelveDataProvider(api_key="test_key")
            result = provider.get_quotes(["AAPL", "GOOGL", "MSFT"])

            assert len(result) == 3
            assert all(r["last_price"] == 150.0 for r in result)

    def test_get_quotes_handles_non_ok_status(self):
        """get_quotes should skip responses with status != 'ok'."""
        with patch("httpx.get") as mock_get:
            mock_get.return_value = MagicMock(status_code=200, json=MagicMock(return_value={"status": "error"}))

            provider = TwelveDataProvider(api_key="test_key")
            result = provider.get_quotes(["AAPL"])

            assert len(result) == 1
            assert result[0]["last_price"] == 0.0


class TestTwelveDataGetHistoricalOhlcv:
    """Tests for get_historical_ohlcv against verified /time_series schema."""

    def test_get_historical_ohlcv_returns_normalized_values(self):
        """get_historical_ohlcv should return properly normalized OHLCV data."""
        mock_time_series = {
            "meta": {
                "symbol": "AAPL",
                "interval": "1day",
                "currency": "USD",
                "exchange_timezone": "America/New_York",
                "exchange": "NASDAQ",
                "mic_code": "XNMS",
                "type": "Common Stock",
            },
            "values": [
                {
                    "datetime": "2024-01-15",
                    "open": "187.14999",
                    "high": "189.50000",
                    "low": "186.20000",
                    "close": "188.50000",
                    "volume": "82488700",
                }
            ],
            "status": "ok",
        }

        with patch("httpx.get") as mock_get:
            mock_get.return_value = MagicMock(status_code=200, json=MagicMock(return_value=mock_time_series))

            provider = TwelveDataProvider(api_key="test_key")
            result = provider.get_historical_ohlcv("AAPL", history_days=1)

            assert len(result) == 1
            assert result[0]["datetime"] == "2024-01-15"
            assert result[0]["open"] == 187.14999
            assert result[0]["close"] == 188.5
            assert result[0]["volume"] == 82488700

    def test_get_historical_ohlcv_raises_on_api_error_status(self):
        """get_historical_ohlcv should raise ValueError when API returns error status."""
        mock_error = {
            "code": 400,
            "message": "Invalid symbol",
            "status": "error",
            "meta": {"symbol": "INVALID"},
        }

        with patch("httpx.get") as mock_get:
            mock_get.return_value = MagicMock(status_code=200, json=MagicMock(return_value=mock_error))

            provider = TwelveDataProvider(api_key="test_key")
            with pytest.raises(ValueError, match="Invalid symbol"):
                provider.get_historical_ohlcv("INVALID", history_days=1)

    def test_get_historical_ohlcv_uses_config_defaults(self):
        """get_historical_ohlcv should use cfg.history_days when history_days is None."""
        mock_time_series = {
            "meta": {"symbol": "AAPL", "interval": "1day", "currency": "USD",
                     "exchange_timezone": "America/New_York", "exchange": "NASDAQ",
                     "mic_code": "XNMS", "type": "Common Stock"},
            "values": [],
            "status": "ok",
        }

        with patch("httpx.get") as mock_get:
            mock_get.return_value = MagicMock(status_code=200, json=MagicMock(return_value=mock_time_series))

            provider = TwelveDataProvider(api_key="test_key")
            provider.get_historical_ohlcv("AAPL")

            # Verify the call was made with params
            assert mock_get.called
            call_args = mock_get.call_args
            assert call_args[1]["params"]["symbol"] == "AAPL"


class TestTwelveDataHistoricalForDate:
    """Tests for _get_historical_for_date fallback logic."""

    def test_returns_normalized_data_on_success(self):
        """_get_historical_for_date should return normalized data on success."""
        mock_response = {
            "meta": {"symbol": "AAPL", "interval": "1day", "currency": "USD",
                     "exchange_timezone": "America/New_York", "exchange": "NASDAQ",
                     "mic_code": "XNMS", "type": "Common Stock"},
            "values": [
                {"datetime": "2024-01-15", "open": "187.15", "high": "189.50",
                 "low": "186.20", "close": "188.50", "volume": "82488700"}
            ],
            "status": "ok",
        }

        with patch("httpx.get") as mock_get:
            mock_get.return_value = MagicMock(status_code=200, json=MagicMock(return_value=mock_response))

            provider = TwelveDataProvider(api_key="test_key")
            result = provider._get_historical_for_date("AAPL", "2024-01-15")

            assert result is not None
            assert len(result) == 1
            assert result[0]["open"] == 187.15

    def test_returns_none_on_failure(self):
        """_get_historical_for_date should return None on HTTP error."""
        with patch("httpx.get") as mock_get:
            mock_get.side_effect = Exception("Not Found")

            provider = TwelveDataProvider(api_key="test_key")
            result = provider._get_historical_for_date("AAPL", "2024-01-15")

            assert result is None
