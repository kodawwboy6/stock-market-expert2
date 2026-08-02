"""Tests for the AlpacaProvider module.

Verifies response handling against the official Alpaca API schema
documented in docs/adr/0005-external-api-documentation.md.
"""

from unittest.mock import MagicMock, patch

import pytest

from stock_market_expert.data.alpaca_provider import AlpacaProvider


def _make_mock_response(data):
    """Create a mock httpx Response that returns *data* when .json() is called."""
    mock = MagicMock()
    mock.status_code = 200
    mock.json.return_value = data
    return mock


class TestAlpacaProviderInit:
    """Tests for AlpacaProvider initialization."""

    def test_uses_env_vars_by_default(self):
        """__init__ should read API keys from environment variables."""
        with patch.dict(
            "os.environ",
            {"ALPACA_API_KEY": "test_key", "ALPACA_SECRET_KEY": "test_secret"},
        ):
            provider = AlpacaProvider()
            assert provider.api_key == "test_key"
            assert provider.secret_key == "test_secret"
            assert provider.base_url == "https://paper-api.alpaca.markets"
            assert provider.market_data_base_url == "https://data.alpaca.markets"

    def test_constructor_params_override_env(self):
        """__init__ constructor params should override environment variables."""
        with patch.dict(
            "os.environ",
            {"ALPACA_API_KEY": "env_key", "ALPACA_SECRET_KEY": "env_secret"},
        ):
            provider = AlpacaProvider(
                api_key="param_key",
                secret_key="param_secret",
                base_url="https://custom.trading.com",
                market_data_base_url="https://custom.data.com",
            )
            assert provider.api_key == "param_key"
            assert provider.secret_key == "param_secret"
            assert provider.base_url == "https://custom.trading.com"
            assert provider.market_data_base_url == "https://custom.data.com"

    def test_raises_on_missing_api_key(self):
        """__init__ should raise ValueError when API key is missing."""
        with patch.dict("os.environ", {"ALPACA_SECRET_KEY": "test_secret"}):
            with pytest.raises(ValueError, match="ALPACA_API_KEY"):
                AlpacaProvider()

    def test_raises_on_missing_secret_key(self):
        """__init__ should raise ValueError when secret key is missing."""
        with patch.dict("os.environ", {"ALPACA_API_KEY": "test_key"}):
            with pytest.raises(ValueError, match="ALPACA_SECRET_KEY"):
                AlpacaProvider()


class TestAlpacaProviderGetRealtimeQuote:
    """Tests for get_realtime_quote against verified /v2/quotes schema.

    Per official API docs (verified live):
    - Endpoint: https://data.alpaca.markets/v2/quotes/{symbol}
    - Response keys: lp (last price), bid, ask, v (volume), t (timestamp)
    """

    def test_uses_market_data_base_url(self):
        """get_realtime_quote should use data.alpaca.markets, not trading API."""
        mock_response = {"lp": "150.00", "bid": "149.99", "ask": "150.01", "v": 100, "t": "2024-01-15T10:00:00Z"}

        with patch("httpx.get") as mock_get:
            mock_get.return_value = _make_mock_response(mock_response)

            provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
            provider.get_realtime_quote("AAPL")

            called_url = mock_get.call_args[0][0]
            assert "data.alpaca.markets" in called_url
            assert "/v2/quotes/AAPL" in called_url

    def test_returns_normalized_quote_data(self):
        """get_realtime_quote should return properly typed quote fields."""
        mock_response = {"lp": "309.029999", "bid": "309.00", "ask": "309.05", "v": 82488700, "t": "2024-01-15T10:00:00Z"}

        with patch("httpx.get") as mock_get:
            mock_get.return_value = _make_mock_response(mock_response)

            provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
            result = provider.get_realtime_quote("AAPL")

            assert result["symbol"] == "AAPL"
            assert result["last_price"] == 309.029999
            assert result["bid"] == 309.0
            assert result["ask"] == 309.05
            assert result["volume"] == 82488700
            assert result["timestamp"] == "2024-01-15T10:00:00Z"
            assert isinstance(result["last_price"], float)
            assert isinstance(result["volume"], int)

    def test_handles_missing_quote_fields_with_defaults(self):
        """get_realtime_quote should use safe defaults for missing response fields."""
        mock_response = {}

        with patch("httpx.get") as mock_get:
            mock_get.return_value = _make_mock_response(mock_response)

            provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
            result = provider.get_realtime_quote("AAPL")

            assert result["last_price"] == 0.0
            assert result["bid"] == 0.0
            assert result["ask"] == 0.0
            assert result["volume"] == 0
            assert result["timestamp"] == ""

    def test_uses_correct_auth_headers(self):
        """get_realtime_quote should send Apca-Api-Key-Id and Apca-Api-Secret-Key headers."""
        mock_response = {"lp": "150.00"}

        with patch("httpx.get") as mock_get:
            mock_get.return_value = _make_mock_response(mock_response)

            provider = AlpacaProvider(api_key="my_key", secret_key="my_secret")
            provider.get_realtime_quote("AAPL")

            headers = mock_get.call_args[1]["headers"]
            assert headers["Apca-Api-Key-Id"] == "my_key"
            assert headers["Apca-Api-Secret-Key"] == "my_secret"


class TestAlpacaProviderGetPortfolioBalance:
    """Tests for get_portfolio_balance against verified API schemas.

    /v2/account keys: cash, equity, buying_power, portfolio_value, status, currency, shorting_enabled, multiplier
    /v2/positions: array of {symbol, qty, avg_entry_price, market_value, unrealized_pl}
    """

    def test_returns_account_fields_from_verified_schema(self):
        """get_portfolio_balance should extract all verified account fields."""
        mock_account = {
            "cash": "100000",
            "equity": "100000",
            "buying_power": "400000",
            "portfolio_value": "105000",
            "status": "ACTIVE",
            "currency": "USD",
            "shorting_enabled": True,
            "multiplier": "2",
        }
        mock_positions = []

        with patch("httpx.get") as mock_get:
            mock_get.side_effect = [_make_mock_response(mock_account), _make_mock_response(mock_positions)]

            provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
            result = provider.get_portfolio_balance()

            assert result["cash"] == 100000.0
            assert result["equity"] == 100000.0
            assert result["buying_power"] == 400000.0
            assert result["portfolio_value"] == 105000.0
            assert result["status"] == "ACTIVE"
            assert result["currency"] == "USD"
            assert result["shorting_enabled"] is True
            assert result["multiplier"] == "2"
            assert result["positions"] == {}

    def test_uses_trading_api_for_account_and_positions(self):
        """get_portfolio_balance should use paper-api.alpaca.markets for /v2/account and /v2/positions."""
        mock_account = {
            "cash": "100000", "equity": "100000", "buying_power": "400000",
            "portfolio_value": "100000", "status": "ACTIVE", "currency": "USD",
            "shorting_enabled": False, "multiplier": "2",
        }
        mock_positions = []

        with patch("httpx.get") as mock_get:
            mock_get.side_effect = [_make_mock_response(mock_account), _make_mock_response(mock_positions)]

            provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
            provider.get_portfolio_balance()

            calls = mock_get.call_args_list
            account_call = calls[0]
            assert "paper-api.alpaca.markets" in account_call[0][0]
            assert "/v2/account" in account_call[0][0]

            positions_call = calls[1]
            assert "paper-api.alpaca.markets" in positions_call[0][0]
            assert "/v2/positions" in positions_call[0][0]

    def test_handles_positions_from_verified_schema(self):
        """get_portfolio_balance should parse position objects correctly."""
        mock_account = {
            "cash": "100000", "equity": "105000", "buying_power": "400000",
            "portfolio_value": "105000", "status": "ACTIVE", "currency": "USD",
            "shorting_enabled": False, "multiplier": "2",
        }
        mock_positions = [
            {
                "symbol": "AAPL",
                "qty": "10",
                "avg_entry_price": "150.00",
                "market_value": "1550.00",
                "unrealized_pl": "50.00",
            }
        ]

        with patch("httpx.get") as mock_get:
            mock_get.side_effect = [_make_mock_response(mock_account), _make_mock_response(mock_positions)]

            provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
            result = provider.get_portfolio_balance()

            assert "AAPL" in result["positions"]
            assert result["positions"]["AAPL"]["qty"] == 10.0
            assert result["positions"]["AAPL"]["avg_entry_price"] == 150.0
            assert result["positions"]["AAPL"]["current_price"] == 155.0
            assert result["positions"]["AAPL"]["unrealized_pl"] == 50.0

    def test_handles_zero_quantity_position(self):
        """get_portfolio_balance should avoid division by zero for zero qty positions."""
        mock_account = {
            "cash": "100000", "equity": "100000", "buying_power": "400000",
            "portfolio_value": "100000", "status": "ACTIVE", "currency": "USD",
            "shorting_enabled": False, "multiplier": "2",
        }
        mock_positions = [
            {
                "symbol": "GOOGL",
                "qty": "0",
                "avg_entry_price": "0",
                "market_value": "0",
                "unrealized_pl": "0",
            }
        ]

        with patch("httpx.get") as mock_get:
            mock_get.side_effect = [_make_mock_response(mock_account), _make_mock_response(mock_positions)]

            provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
            result = provider.get_portfolio_balance()

            assert "GOOGL" in result["positions"]
            assert result["positions"]["GOOGL"]["current_price"] == 0


class TestAlpacaProviderGetHistoricalQuotes:
    """Tests for get_historical_quotes against verified /v2/stocks/{symbol}/trades schema.

    Per official API docs (verified live):
    - Endpoint: https://data.alpaca.markets/v2/stocks/{symbol}/trades
    - Response: {next_page_token, symbol, trades}
    - Each trade: T (timestamp), P (price), S (size)
    """

    def test_uses_market_data_base_url(self):
        """get_historical_quotes should use data.alpaca.markets, not trading API."""
        mock_response = {
            "next_page_token": None,
            "symbol": "AAPL",
            "trades": [{"T": "2024-01-15T10:00:00Z", "P": 150.00, "S": 100}],
        }

        with patch("httpx.get") as mock_get:
            mock_get.return_value = _make_mock_response(mock_response)

            provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
            provider.get_historical_quotes("AAPL", "2024-01-15", "2024-01-15")

            called_url = mock_get.call_args[0][0]
            assert "data.alpaca.markets" in called_url
            assert "/v2/stocks/AAPL/trades" in called_url

    def test_returns_normalized_trade_data(self):
        """get_historical_quotes should return properly typed trade data."""
        mock_response = {
            "next_page_token": None,
            "symbol": "AAPL",
            "trades": [
                {"T": "2024-01-15T10:00:00Z", "P": 150.00, "S": 100},
                {"T": "2024-01-15T10:01:00Z", "P": 150.50, "S": 200},
            ],
        }

        with patch("httpx.get") as mock_get:
            mock_get.return_value = _make_mock_response(mock_response)

            provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
            result = provider.get_historical_quotes("AAPL", "2024-01-15", "2024-01-15")

            assert len(result) == 2
            assert result[0]["datetime"] == "2024-01-15T10:00:00Z"
            assert result[0]["open"] == 150.0
            assert result[0]["high"] == 150.0
            assert result[0]["low"] == 150.0
            assert result[0]["close"] == 150.0
            assert result[0]["volume"] == 100
            assert isinstance(result[0]["open"], float)
            assert isinstance(result[0]["volume"], int)

            assert result[1]["open"] == 150.5
            assert result[1]["volume"] == 200

    def test_handles_empty_trades_list(self):
        """get_historical_quotes should return empty list when no trades."""
        mock_response = {"next_page_token": None, "symbol": "AAPL", "trades": []}

        with patch("httpx.get") as mock_get:
            mock_get.return_value = _make_mock_response(mock_response)

            provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
            result = provider.get_historical_quotes("AAPL", "2024-01-15", "2024-01-15")

            assert result == []

    def test_handles_missing_trade_fields_with_defaults(self):
        """get_historical_quotes should use safe defaults for missing trade fields."""
        mock_response = {"next_page_token": None, "symbol": "AAPL", "trades": [{}]}

        with patch("httpx.get") as mock_get:
            mock_get.return_value = _make_mock_response(mock_response)

            provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
            result = provider.get_historical_quotes("AAPL", "2024-01-15", "2024-01-15")

            assert len(result) == 1
            assert result[0]["datetime"] == ""
            assert result[0]["open"] == 0.0
            assert result[0]["volume"] == 0

    def test_uses_correct_auth_headers(self):
        """get_historical_quotes should send Apca-Api-Key-Id and Apca-Api-Secret-Key headers."""
        mock_response = {"next_page_token": None, "symbol": "AAPL", "trades": []}

        with patch("httpx.get") as mock_get:
            mock_get.return_value = _make_mock_response(mock_response)

            provider = AlpacaProvider(api_key="my_key", secret_key="my_secret")
            provider.get_historical_quotes("AAPL", "2024-01-15", "2024-01-15")

            headers = mock_get.call_args[1]["headers"]
            assert headers["Apca-Api-Key-Id"] == "my_key"
            assert headers["Apca-Api-Secret-Key"] == "my_secret"

    def test_sends_request_params(self):
        """get_historical_quotes should pass start, end, limit as query params."""
        mock_response = {"next_page_token": None, "symbol": "AAPL", "trades": []}

        with patch("httpx.get") as mock_get:
            mock_get.return_value = _make_mock_response(mock_response)

            provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
            provider.get_historical_quotes("AAPL", "2024-01-15", "2024-01-20")

            params = mock_get.call_args[1]["params"]
            assert params["start"] == "2024-01-15"
            assert params["end"] == "2024-01-20"
            assert params["limit"] == 1000


class TestAlpacaProviderResponseKeyMapping:
    """Tests verifying response key mapping matches verified API schema."""

    def test_quote_response_key_lp_maps_to_last_price(self):
        """Quote 'lp' key should map to 'last_price' in result."""
        mock_response = {"lp": "309.029999"}

        with patch("httpx.get") as mock_get:
            mock_get.return_value = _make_mock_response(mock_response)

            provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
            result = provider.get_realtime_quote("AAPL")

            assert result["last_price"] == 309.029999

    def test_quote_response_key_v_maps_to_volume(self):
        """Quote 'v' key should map to 'volume' in result."""
        mock_response = {"v": 82488700}

        with patch("httpx.get") as mock_get:
            mock_get.return_value = _make_mock_response(mock_response)

            provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
            result = provider.get_realtime_quote("AAPL")

            assert result["volume"] == 82488700

    def test_trade_response_key_T_maps_to_datetime(self):
        """Trade 'T' key should map to 'datetime' in result."""
        mock_response = {"next_page_token": None, "symbol": "AAPL", "trades": [{"T": "2024-01-15T10:00:00Z"}]}

        with patch("httpx.get") as mock_get:
            mock_get.return_value = _make_mock_response(mock_response)

            provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
            result = provider.get_historical_quotes("AAPL", "2024-01-15", "2024-01-15")

            assert result[0]["datetime"] == "2024-01-15T10:00:00Z"

    def test_trade_response_key_P_maps_to_open_high_low_close(self):
        """Trade 'P' key should map to OHLC fields in result."""
        mock_response = {"next_page_token": None, "symbol": "AAPL", "trades": [{"P": 150.00}]}

        with patch("httpx.get") as mock_get:
            mock_get.return_value = _make_mock_response(mock_response)

            provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
            result = provider.get_historical_quotes("AAPL", "2024-01-15", "2024-01-15")

            assert result[0]["open"] == 150.0
            assert result[0]["high"] == 150.0
            assert result[0]["low"] == 150.0
            assert result[0]["close"] == 150.0

    def test_trade_response_key_S_maps_to_volume(self):
        """Trade 'S' key should map to 'volume' in result."""
        mock_response = {"next_page_token": None, "symbol": "AAPL", "trades": [{"S": 100}]}

        with patch("httpx.get") as mock_get:
            mock_get.return_value = _make_mock_response(mock_response)

            provider = AlpacaProvider(api_key="test_key", secret_key="test_secret")
            result = provider.get_historical_quotes("AAPL", "2024-01-15", "2024-01-15")

            assert result[0]["volume"] == 100
