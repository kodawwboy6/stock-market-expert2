"""Finnhub news provider module.

Fetches company news from Finnhub's /company-news API endpoint.
Includes retry with exponential backoff and fallback to previous days.
"""

import dataclasses
from datetime import date, timedelta
from typing import Optional

import httpx

from stock_market_expert.config.loader import load_config


@dataclasses.dataclass
class CompanyNews:
    """A single company news item from Finnhub."""

    headline: str
    url: str
    source: str
    time_published: str
    summary: Optional[str] = None
    related: Optional[list[str]] = None
    symbols: Optional[list[str]] = None
    category: Optional[str] = None


class FinnhubNewsProvider:
    """Provider for fetching company news from Finnhub.

    Fetches company news from Finnhub's /company-news API endpoint.
    """

    BASE_URL = "https://finnhub.io/api/v1"

    def __init__(self, api_key: str):
        """Initialize the provider.

        Args:
            api_key: Finnhub API key.
        """
        self.api_key = api_key

    def fetch_company_news(
        self,
        symbol: str,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> tuple[list[CompanyNews], bool]:
        """Fetch company news for a given symbol.

        Args:
            symbol: Stock symbol (e.g., "AAPL").
            date_from: Start date (YYYY-MM-DD).
            date_to: End date (YYYY-MM-DD).

        Returns:
            List of parsed CompanyNews objects.

        Raises:
            Exception: If the API request fails.
        """
        params = {
            "token": self.api_key,
            "symbol": symbol,
        }
        if date_from:
            params["from"] = date_from
        if date_to:
            params["to"] = date_to

        response = httpx.get(f"{self.BASE_URL}/company-news", params=params)
        response.raise_for_status()
        data = response.json()

        news_items = []
        for item in data:
            news_items.append(
                CompanyNews(
                    headline=item.get("headline", ""),
                    url=item.get("url", ""),
                    source=item.get("source", ""),
                    time_published=item.get("datetime", ""),
                    summary=item.get("summary", None),
                    related=item.get("related", None),
                    symbols=item.get("symbols", None),
                    category=item.get("category", None),
                )
            )

        return news_items


def fetch_company_news_with_retry(
    api_key: str,
    symbol: str,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    max_retries: Optional[int] = None,
    fallback_days: Optional[int] = None,
) -> tuple[list[CompanyNews], bool]:
    """Fetch company news with retry and fallback to previous days.

    Tries up to max_retries times with exponential backoff.
    If all retries fail, falls back to news from fallback_days
    days ago. Repeats fallback up to 5 days back.

    Args:
        api_key: Finnhub API key.
        symbol: Stock symbol (e.g., "AAPL").
        date_from: Start date (YYYY-MM-DD).
        date_to: End date (YYYY-MM-DD).
        max_retries: Number of retries per date attempt. Defaults to RETRY_MAX env var.
        fallback_days: How many days back to start falling back. Defaults to 1.

    Returns:
        Tuple of (list of CompanyNews objects, bool indicating if fallback was used).
    """
    import logging
    import time

    logger = logging.getLogger(__name__)
    cfg = load_config()
    max_retries = max_retries if max_retries is not None else cfg.retry_max
    fallback_days = fallback_days if fallback_days is not None else 1

    provider = FinnhubNewsProvider(api_key)

    # Try today/today's range first
    last_exception = None
    for attempt in range(max_retries + 1):
        try:
            items = provider.fetch_company_news(
                symbol=symbol,
                date_from=date_from,
                date_to=date_to,
            )
            if items:
                logger.info(f"Fetched {len(items)} company news items for {symbol}")
                return items, False
            logger.warning(f"No company news for {symbol}, trying fallback")
        except Exception as e:
            last_exception = e
            if attempt < max_retries:
                delay = min(cfg.retry_delay_factor * (2 ** attempt), cfg.retry_max_delay)
                logger.warning(
                    f"Attempt {attempt + 1}/{max_retries + 1} failed: {e}. "
                    f"Retrying in {delay:.1f}s..."
                )
                time.sleep(delay)
            else:
                logger.warning(f"All {max_retries} retries failed for {symbol}: {e}")

    # Fall back to previous days
    for days_back in range(1, fallback_days + 6):
        fallback_from = (date.today() - timedelta(days=days_back)).isoformat()
        fallback_to = (date.today() - timedelta(days=max(days_back - 1, 0))).isoformat()
        logger.info(f"Falling back to company news for {symbol} ({fallback_from} to {fallback_to})")

        for attempt in range(max_retries + 1):
            try:
                items = provider.fetch_company_news(
                    symbol=symbol,
                    date_from=fallback_from,
                    date_to=fallback_to,
                )
                if items:
                    logger.info(
                        f"Fetched {len(items)} company news items for {symbol} (fallback)"
                    )
                    return items, True
                logger.warning(
                    f"No company news for {symbol} on fallback date, trying next"
                )
            except Exception as e:
                last_exception = e
                if attempt < max_retries:
                    delay = min(cfg.retry_delay_factor * (2 ** attempt), cfg.retry_max_delay)
                    logger.warning(
                        f"Fallback attempt {attempt + 1}/{max_retries + 1} failed: {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)
                else:
                    logger.warning(
                        f"All retries failed for {symbol} on fallback: {e}"
                    )

    logger.error(
        f"Failed to fetch company news for {symbol} after {max_retries} retries "
        f"and {fallback_days + 5} fallback days. Last error: {last_exception}"
    )
    return [], False
