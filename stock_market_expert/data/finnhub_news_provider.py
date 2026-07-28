"""Finnhub news provider module.

Fetches company news from Finnhub's /company-news API endpoint.
"""

import dataclasses
from typing import Optional

import httpx


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
    ) -> list[CompanyNews]:
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
