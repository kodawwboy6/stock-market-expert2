"""Twelve Data provider for historical OHLCV data.

Fetches historical price data for technical analysis.
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx

from stock_market_expert.errors.handler import retry_with_backoff


class TwelveDataProvider:
    """Client for Twelve Data API.

    Fetches historical OHLCV data for technical indicator computation.
    """

    BASE_URL = "https://api.twelvedata.com"

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the Twelve Data provider.

        Args:
            api_key: Twelve Data API key. Defaults to TWELVE_DATA_API_KEY env var.
        """
        self.api_key = api_key or os.getenv("TWELVE_DATA_API_KEY", "")
        if not self.api_key:
            raise ValueError("TWELVE_DATA_API_KEY environment variable is required")

    def get_historical_ohlcv(
        self,
        symbol: str,
        interval: str = "1day",
        history_days: int = 90,
        fallback_date: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Fetch historical OHLCV data for a symbol.

        Args:
            symbol: Stock ticker symbol (e.g., "AAPL").
            interval: Time interval — "1min", "5min", "15min", "1hour", "1day".
            history_days: Number of days of history to fetch.
            fallback_date: Date string for fallback data if all retries fail.

        Returns:
            List of OHLCV dicts with keys: datetime, open, high, low, close, volume.

        Raises:
            Exception: If all retries fail and no fallback is provided.
        """
        end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        start_date = (datetime.now(timezone.utc) - timedelta(days=history_days)).strftime("%Y-%m-%d")

        url = f"{self.BASE_URL}/time_series"
        params = {
            "symbol": symbol,
            "interval": interval,
            "start_date": start_date,
            "end_date": end_date,
            "outputsize": max(history_days, 90),
            "format": "JSON",
            "apikey": self.api_key,
        }

        def _fetch():
            response = httpx.get(url, params=params, timeout=30.0)
            response.raise_for_status()
            data = response.json()
            if data.get("status") == "error":
                raise ValueError(f"Twelve Data API error: {data.get('message', 'unknown error')}")
            return data.get("values", [])

        fallback_data = None
        if fallback_date:
            fallback_data = self._get_historical_for_date(symbol, fallback_date)

        result = retry_with_backoff(
            func=_fetch,
            max_retries=3,
            fallback_date=fallback_date,
            fallback_data=fallback_data,
        )

        return self._normalize_ohlcv(result)

    def _get_historical_for_date(self, symbol: str, date: str) -> Optional[list[dict[str, Any]]]:
        """Fetch historical data for a specific date as fallback."""
        url = f"{self.BASE_URL}/time_series"
        params = {
            "symbol": symbol,
            "interval": "1day",
            "start_date": date,
            "end_date": date,
            "outputsize": 1,
            "format": "JSON",
            "apikey": self.api_key,
        }
        try:
            response = httpx.get(url, params=params, timeout=30.0)
            response.raise_for_status()
            data = response.json()
            if data.get("status") == "ok":
                return self._normalize_ohlcv(data.get("values", []))
        except Exception:
            pass
        return None

    def _normalize_ohlcv(self, raw_data: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Normalize raw Twelve Data response to standard OHLCV format."""
        normalized = []
        for item in raw_data:
            normalized.append({
                "datetime": item.get("datetime", ""),
                "open": float(item.get("open", 0)),
                "high": float(item.get("high", 0)),
                "low": float(item.get("low", 0)),
                "close": float(item.get("close", 0)),
                "volume": int(item.get("volume", 0)),
            })
        return normalized

    def get_quotes(self, symbols: list[str]) -> list[dict[str, Any]]:
        """Fetch real-time quotes for multiple symbols.

        Args:
            symbols: List of stock ticker symbols.

        Returns:
            List of quote dicts with keys: symbol, last_price, bid, ask, volume.
        """
        quotes = []
        for symbol in symbols:
            url = f"{self.BASE_URL}/price"
            params = {
                "symbol": symbol,
                "apikey": self.api_key,
            }
            try:
                response = httpx.get(url, params=params, timeout=15.0)
                response.raise_for_status()
                data = response.json()
                if data.get("status") == "ok":
                    quotes.append({
                        "symbol": symbol,
                        "last_price": float(data.get("price", 0)),
                        "bid": float(data.get("bid", 0)),
                        "ask": float(data.get("ask", 0)),
                        "volume": int(data.get("volume", 0)),
                    })
            except Exception as e:
                quotes.append({
                    "symbol": symbol,
                    "last_price": 0,
                    "bid": 0,
                    "ask": 0,
                    "volume": 0,
                    "error": str(e),
                })
        return quotes
