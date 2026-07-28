"""Tests for the AlphaVantageNewsProvider module."""

from unittest.mock import MagicMock, patch

import pytest

from stock_market_expert.data.alpha_vantage_news_provider import (
    AlphaVantageNewsProvider,
    NewsItem,
)


class TestAlphaVantageNewsProvider:
    """Tests for the AlphaVantageNewsProvider class."""

    def test_fetch_news_returns_parsed_items(self):
        """Fetching news should return parsed NewsItem objects."""
        mock_response = {
            "feed": [
                {
                    "title": "Test Headline",
                    "body": "Test body content",
                    "categories": ["technology"],
                    "source": "Test Source",
                    "time_published": "2024-01-15T10:00:00Z",
                    "sentiment": "positive",
                    "url": "https://example.com/test",
                }
            ]
        }

        with patch("httpx.get") as mock_get:
            mock_get.return_value = MagicMock(status_code=200, json=MagicMock(return_value=mock_response))

            provider = AlphaVantageNewsProvider(api_key="test_key")
            result = provider.fetch_news(category="technology")

            assert len(result) == 1
            assert isinstance(result[0], NewsItem)
            assert result[0].headline == "Test Headline"
            assert result[0].body == "Test body content"
            assert result[0].categories == ["technology"]
            assert result[0].source == "Test Source"
            assert result[0].time_published == "2024-01-15T10:00:00Z"
            assert result[0].sentiment == "positive"
            assert result[0].url == "https://example.com/test"

    def test_fetch_news_handles_empty_response(self):
        """Fetching news with no results should return an empty list."""
        mock_response = {"feed": []}

        with patch("httpx.get") as mock_get:
            mock_get.return_value = MagicMock(status_code=200, json=MagicMock(return_value=mock_response))

            provider = AlphaVantageNewsProvider(api_key="test_key")
            result = provider.fetch_news(category="technology")

            assert result == []

    def test_fetch_news_raises_on_api_error(self):
        """Fetching news with an API error should raise an exception."""
        with patch("httpx.get") as mock_get:
            mock_get.side_effect = Exception("API Error")

            provider = AlphaVantageNewsProvider(api_key="test_key")

            with pytest.raises(Exception, match="API Error"):
                provider.fetch_news(category="technology")

    def test_fetch_news_calls_correct_api_url(self):
        """Fetching news should call the correct Alpha Vantage API endpoint."""
        mock_response = {"feed": []}

        with patch("httpx.get") as mock_get:
            mock_get.return_value = MagicMock(status_code=200, json=MagicMock(return_value=mock_response))

            provider = AlphaVantageNewsProvider(api_key="test_key")
            provider.fetch_news(category="technology")

            mock_get.assert_called_once()
            call_args = mock_get.call_args
            assert "alphavantage" in call_args[0][0]
            assert "test_key" in call_args[1]["params"]["apikey"]
            assert call_args[1]["params"]["categories"] == "technology"

    def test_fetch_news_with_date_filter(self):
        """Fetching news with a date filter should include the date in the request."""
        mock_response = {"feed": []}

        with patch("httpx.get") as mock_get:
            mock_get.return_value = MagicMock(status_code=200, json=MagicMock(return_value=mock_response))

            provider = AlphaVantageNewsProvider(api_key="test_key")
            provider.fetch_news(category="technology", date="2024-01-15")

            mock_get.assert_called_once()
            call_args = mock_get.call_args
            assert call_args[1]["params"]["time_from"] == "2024-01-15T0000"
            assert call_args[1]["params"]["time_to"] == "2024-01-15T2359"
