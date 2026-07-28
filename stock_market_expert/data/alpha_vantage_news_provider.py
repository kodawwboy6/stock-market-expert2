"""Alpha Vantage news provider module.

Fetches technology news from Alpha Vantage's /news API endpoint.
"""

import dataclasses
from typing import Optional

import httpx


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
    ) -> list[NewsItem]:
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
