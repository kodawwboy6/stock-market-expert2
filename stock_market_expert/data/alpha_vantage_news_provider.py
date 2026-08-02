"""Alpha Vantage news provider module.

Fetches technology news from Alpha Vantage's /news API endpoint.
Includes retry with exponential backoff and fallback to previous days.
"""

import dataclasses
from datetime import date, timedelta
from typing import Optional

import httpx

from stock_market_expert.config.loader import load_config


@dataclasses.dataclass
class NewsItem:
    """A single news item from Alpha Vantage."""

    headline: str
    body: str
    categories: list[str]
    source: str
    time_published: str
    sentiment: Optional[str] = None
    url: Optional[str] = None


class AlphaVantageNewsProvider:
    """Provider for fetching news from Alpha Vantage.

    Fetches technology news from Alpha Vantage's /news API endpoint.
    """

    BASE_URL = "https://www.alphavantage.co/query"

    def __init__(self, api_key: str):
        """Initialize the provider.

        Args:
            api_key: Alpha Vantage API key.
        """
        self.api_key = api_key

    def fetch_news(
        self,
        category: str,
        date: Optional[str] = None,
    ) -> tuple[list[NewsItem], bool]:
        """Fetch news for a given category.

        Args:
            category: News category (e.g., "technology").
            date: Optional date filter (YYYY-MM-DD).

        Returns:
            List of parsed NewsItem objects.

        Raises:
            Exception: If the API request fails.
        """
        params = {
            "function": "NEWS_SENTIMENT",
            "apikey": self.api_key,
            "categories": category,
        }
        if date:
            params["time_from"] = date + "T0000"
            params["time_to"] = date + "T2359"

        response = httpx.get(self.BASE_URL, params=params)
        response.raise_for_status()
        data = response.json()

        feed = data.get("feed", [])
        news_items = []
        for item in feed:
            sentiment = item.get("sentiment", None)
            if isinstance(sentiment, dict):
                sentiment = sentiment.get("sentiment", None)

            news_items.append(
                NewsItem(
                    headline=item.get("title", ""),
                    body=item.get("body", ""),
                    categories=item.get("categories", []),
                    source=item.get("source", ""),
                    time_published=item.get("time_published", ""),
                    sentiment=sentiment,
                    url=item.get("url", None),
                )
            )

        return news_items


class NewsProviderError(Exception):
    """Raised when a news provider encounters an error."""


def fetch_news_with_retry(
    api_key: str,
    category: str,
    max_retries: Optional[int] = None,
    fallback_days: Optional[int] = None,
) -> tuple[list[NewsItem], bool]:
    """Fetch news with retry and fallback to previous days.

    Tries up to max_retries times with exponential backoff.
    If all retries fail, falls back to news from fallback_days
    days ago. Repeats fallback up to 5 days back.

    Args:
        api_key: Alpha Vantage API key.
        category: News category (e.g., "technology").
        max_retries: Number of retries per date attempt. Defaults to RETRY_MAX env var.
        fallback_days: How many days back to start falling back. Defaults to 1.

    Returns:
        Tuple of (list of NewsItem objects, bool indicating if fallback was used).
    """
    import logging
    import time

    from stock_market_expert.errors.handler import retry_with_backoff

    logger = logging.getLogger(__name__)
    cfg = load_config()
    max_retries = max_retries if max_retries is not None else cfg.retry_max
    fallback_days = fallback_days if fallback_days is not None else 1

    provider = AlphaVantageNewsProvider(api_key)

    # Try today first
    last_exception = None
    for attempt in range(max_retries + 1):
        try:
            items = provider.fetch_news(category=category)
            if items:
                logger.info(f"Fetched {len(items)} news items (today)")
                return items, False
            logger.warning(f"No news items returned for today, trying fallback")
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
                logger.warning(f"All {max_retries} retries failed for today: {e}")

    # Fall back to previous days
    for days_back in range(1, fallback_days + 6):
        fallback_date = date.today() - timedelta(days=days_back)
        date_str = fallback_date.isoformat()
        logger.info(f"Falling back to news from {date_str}")

        for attempt in range(max_retries + 1):
            try:
                items = provider.fetch_news(category=category, date=date_str)
                if items:
                    logger.info(
                        f"Fetched {len(items)} news items (fallback: {date_str})"
                    )
                    return items, True
                logger.warning(
                    f"No news items for {date_str}, trying next fallback date"
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
                        f"All retries failed for {date_str}: {e}"
                    )

    logger.error(
        f"Failed to fetch news after {max_retries} retries and "
        f"{fallback_days + 5} fallback days. Last error: {last_exception}"
    )
    return [], False


def fetch_news_with_fallback(
    api_key: str,
    category: str,
    max_retries: Optional[int] = None,
    fallback_data: Optional[list[NewsItem]] = None,
) -> tuple[list[NewsItem], bool]:
    """Fetch news with retry and optional static fallback data.

    Tries up to max_retries times with exponential backoff.
    If all retries fail, returns fallback_data if provided,
    otherwise returns empty list.

    Args:
        api_key: Alpha Vantage API key.
        category: News category (e.g., "technology").
        max_retries: Number of retries. Defaults to RETRY_MAX env var.
        fallback_data: Static data to return if API fails.

    Returns:
        Tuple of (list of NewsItem objects, bool indicating if fallback was used).
    """
    import logging
    import time

    logger = logging.getLogger(__name__)
    cfg = load_config()
    max_retries = max_retries if max_retries is not None else cfg.retry_max

    provider = AlphaVantageNewsProvider(api_key)

    for attempt in range(max_retries + 1):
        try:
            items = provider.fetch_news(category=category)
            if items:
                return items, False
        except Exception as e:
            if attempt < max_retries:
                delay = min(cfg.retry_delay_factor * (2 ** attempt), cfg.retry_max_delay)
                logger.warning(
                    f"Attempt {attempt + 1}/{max_retries + 1} failed: {e}. "
                    f"Retrying in {delay:.1f}s..."
                )
                time.sleep(delay)
            else:
                logger.warning(f"All {max_retries} retries failed: {e}")

    if fallback_data is not None:
        logger.info("Returning fallback data")
        return fallback_data, True
    logger.warning("No fallback data, returning empty list")
    return [], False
