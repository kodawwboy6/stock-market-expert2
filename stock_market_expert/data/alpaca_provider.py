"""Alpaca provider for limited real-time quote data.

Fetches real-time quotes, historical trade data, and account balance
from Alpaca APIs. Trading endpoints use the trading API base URL,
while market data endpoints use the market data API base URL.
"""

import os
from typing import Any, Optional

import httpx

from stock_market_expert.config.loader import load_config
from stock_market_expert.errors.handler import retry_with_backoff


class AlpacaProvider:
    """Client for Alpaca trading and market data APIs.

    Provides real-time quotes, historical trades, and portfolio balance
    for execution. Trading endpoints use the trading API, market data
    endpoints use the market data API.
    """

    DEFAULT_BASE_URL = "https://paper-api.alpaca.markets"
    DEFAULT_MARKET_DATA_BASE_URL = "https://data.alpaca.markets"

    def __init__(
        self,
        api_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        base_url: Optional[str] = None,
        market_data_base_url: Optional[str] = None,
    ):
        """Initialize the Alpaca provider.

        Args:
            api_key: Alpaca API key. Defaults to ALPACA_API_KEY env var.
            secret_key: Alpaca secret key. Defaults to ALPACA_SECRET_KEY env var.
            base_url: Trading API base URL. Defaults to ALPACA_BASE_URL env var.
            market_data_base_url: Market data API base URL.
                Defaults to ALPACA_MARKET_DATA_BASE_URL env var.
        """
        self.api_key = api_key or os.getenv("ALPACA_API_KEY", "")
        self.secret_key = secret_key or os.getenv("ALPACA_SECRET_KEY", "")
        self.base_url = base_url or os.getenv("ALPACA_BASE_URL", self.DEFAULT_BASE_URL)
        self.market_data_base_url = market_data_base_url or os.getenv(
            "ALPACA_MARKET_DATA_BASE_URL", self.DEFAULT_MARKET_DATA_BASE_URL
        )

        if not self.api_key or not self.secret_key:
            raise ValueError("ALPACA_API_KEY and ALPACA_SECRET_KEY environment variables are required")

    def get_realtime_quote(self, symbol: str) -> dict[str, Any]:
        """Fetch real-time quote for a single symbol.

        Uses the market data API (data.alpaca.markets) for quotes.

        Args:
            symbol: Stock ticker symbol.

        Returns:
            Quote dict with keys: symbol, last_price, bid, ask, volume, timestamp.

        Raises:
            Exception: If the API request fails.
        """
        url = f"{self.market_data_base_url}/v2/quotes/{symbol}"
        headers = {
            "Apca-Api-Key-Id": self.api_key,
            "Apca-Api-Secret-Key": self.secret_key,
        }

        def _fetch():
            response = httpx.get(url, headers=headers, timeout=15.0)
            response.raise_for_status()
            return response.json()

        result = retry_with_backoff(func=_fetch)

        return {
            "symbol": symbol,
            "last_price": float(result.get("lp", 0)),
            "bid": float(result.get("bid", 0)),
            "ask": float(result.get("ask", 0)),
            "volume": int(result.get("v", 0)),
            "timestamp": result.get("t", ""),
        }

    def get_portfolio_balance(self) -> dict[str, Any]:
        """Fetch current portfolio balance and positions.

        Uses the trading API (paper-api.alpaca.markets) for account
        and positions endpoints.

        Returns:
            Dict with portfolio cash, equity, and positions per symbol.
        """
        url = f"{self.base_url}/v2/account"
        headers = {
            "Apca-Api-Key-Id": self.api_key,
            "Apca-Api-Secret-Key": self.secret_key,
        }

        def _fetch_account():
            response = httpx.get(url, headers=headers, timeout=15.0)
            response.raise_for_status()
            return response.json()

        def _fetch_positions():
            pos_url = f"{self.base_url}/v2/positions"
            response = httpx.get(pos_url, headers=headers, timeout=15.0)
            response.raise_for_status()
            return response.json()

        account = retry_with_backoff(func=_fetch_account)
        positions = retry_with_backoff(func=_fetch_positions)

        return {
            "cash": float(account.get("cash", 0)),
            "equity": float(account.get("equity", 0)),
            "buying_power": float(account.get("buying_power", 0)),
            "portfolio_value": float(account.get("portfolio_value", 0)),
            "status": account.get("status", ""),
            "currency": account.get("currency", ""),
            "shorting_enabled": account.get("shorting_enabled", False),
            "multiplier": account.get("multiplier", ""),
            "positions": {
                pos["symbol"]: {
                    "qty": float(pos["qty"]),
                    "avg_entry_price": float(pos["avg_entry_price"]),
                    "current_price": float(pos["market_value"]) / abs(float(pos["qty"])) if float(pos["qty"]) != 0 else 0,
                    "unrealized_pl": float(pos["unrealized_pl"]),
                }
                for pos in positions
            },
        }

    def get_historical_quotes(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        timeframe: str = "1D",
    ) -> list[dict[str, Any]]:
        """Fetch historical trade data for a symbol.

        Uses the market data API (data.alpaca.markets) for trade data.

        Args:
            symbol: Stock ticker symbol.
            start_date: Start date in YYYY-MM-DD format.
            end_date: End date in YYYY-MM-DD format.
            timeframe: Bar size — "1Min", "5Min", "15Min", "1H", "1D".

        Returns:
            List of bar dicts with keys: datetime, open, high, low, close, volume.
        """
        url = f"{self.market_data_base_url}/v2/stocks/{symbol}/trades"
        headers = {
            "Apca-Api-Key-Id": self.api_key,
            "Apca-Api-Secret-Key": self.secret_key,
        }
        params = {
            "start": start_date,
            "end": end_date,
            "limit": 1000,
        }

        def _fetch():
            response = httpx.get(url, headers=headers, params=params, timeout=30.0)
            response.raise_for_status()
            return response.json()

        response = retry_with_backoff(func=_fetch)
        trades = response.get("trades", [])

        # Normalize to OHLCV format
        return [
            {
                "datetime": trade.get("T", ""),
                "open": float(trade.get("P", 0)),
                "high": float(trade.get("P", 0)),
                "low": float(trade.get("P", 0)),
                "close": float(trade.get("P", 0)),
                "volume": int(trade.get("S", 0)),
            }
            for trade in trades
        ]
