"""Tests for the FinnhubNewsProvider module."""

from unittest.mock import MagicMock, patch

import pytest

from stock_market_expert.data.finnhub_news_provider import (
    FinnhubNewsProvider,
    CompanyNews,
)


class TestFinnhubNewsProvider:
    """Tests for the FinnhubNewsProvider class."""

    def test_fetch_company_news_returns_parsed_items(self):
        """Fetching company news should return parsed CompanyNews objects."""
        mock_response = [
            {
                "headline": "Test Headline",
                "url": "https://example.com/test",
                "source": "Test Source",
                "datetime": 1705312800,
                "summary": "Test summary",
                "related": "AAPL",
                "category": "general",
                "id": 12345,
            }
        ]

        with patch("httpx.get") as mock_get:
            mock_get.return_value = MagicMock(status_code=200, json=MagicMock(return_value=mock_response))

            provider = FinnhubNewsProvider(api_key="test_key")
            result = provider.fetch_company_news(symbol="AAPL")

            assert len(result) == 1
            assert isinstance(result[0], CompanyNews)
            assert result[0].headline == "Test Headline"
            assert result[0].url == "https://example.com/test"
            assert result[0].source == "Test Source"
            assert result[0].datetime == 1705312800
            assert result[0].summary == "Test summary"
            assert result[0].related == "AAPL"
            assert result[0].category == "general"
            assert result[0].id == 12345
            assert result[0].symbol == "AAPL"

    def test_fetch_company_news_handles_empty_response(self):
        """Fetching company news with no results should return an empty list."""
        mock_response = []

        with patch("httpx.get") as mock_get:
            mock_get.return_value = MagicMock(status_code=200, json=MagicMock(return_value=mock_response))

            provider = FinnhubNewsProvider(api_key="test_key")
            result = provider.fetch_company_news(symbol="AAPL")

            assert result == []

    def test_fetch_company_news_raises_on_api_error(self):
        """Fetching company news with an API error should raise an exception."""
        with patch("httpx.get") as mock_get:
            mock_get.side_effect = Exception("API Error")

            provider = FinnhubNewsProvider(api_key="test_key")

            with pytest.raises(Exception, match="API Error"):
                provider.fetch_company_news(symbol="AAPL")

    def test_fetch_company_news_calls_correct_api_url(self):
        """Fetching company news should call the correct Finnhub API endpoint."""
        mock_response = []

        with patch("httpx.get") as mock_get:
            mock_get.return_value = MagicMock(status_code=200, json=MagicMock(return_value=mock_response))

            provider = FinnhubNewsProvider(api_key="test_key")
            provider.fetch_company_news(symbol="AAPL")

            mock_get.assert_called_once()
            call_args = mock_get.call_args
            assert "finnhub" in call_args[0][0]
            assert "company-news" in call_args[0][0]
            assert call_args[1]["params"]["symbol"] == "AAPL"

    def test_fetch_company_news_with_date_filter(self):
        """Fetching company news with date filters should include them in the request."""
        mock_response = []

        with patch("httpx.get") as mock_get:
            mock_get.return_value = MagicMock(status_code=200, json=MagicMock(return_value=mock_response))

            provider = FinnhubNewsProvider(api_key="test_key")
            provider.fetch_company_news(symbol="AAPL", date_from="2024-01-01", date_to="2024-01-31")

            mock_get.assert_called_once()
            call_args = mock_get.call_args
            assert call_args[1]["params"]["from"] == "2024-01-01"
            assert call_args[1]["params"]["to"] == "2024-01-31"


class TestFetchCompanyNewsWithRetry:
    """Tests for fetch_company_news_with_retry."""

    def test_returns_news_on_first_try(self):
        """Should return company news on the first successful try."""
        mock_response = [
            {
                "headline": "Test Headline",
                "url": "https://example.com/test",
                "source": "Test Source",
                "datetime": 1705312800,
            }
        ]

        with patch("httpx.get") as mock_get:
            mock_get.return_value = MagicMock(status_code=200, json=MagicMock(return_value=mock_response))

            result, fallback_used = __import__("stock_market_expert.data.finnhub_news_provider", fromlist=["fetch_company_news_with_retry"]).fetch_company_news_with_retry(
                api_key="test_key",
                symbol="AAPL",
                max_retries=3,
                fallback_days=1,
            )

            assert len(result) == 1
            assert result[0].headline == "Test Headline"
            assert not fallback_used
            mock_get.assert_called_once()

    def test_returns_empty_on_failure(self):
        """Should return empty list when all retries fail."""
        with patch("httpx.get") as mock_get:
            mock_get.side_effect = Exception("API Error")

            result, fallback_used = __import__("stock_market_expert.data.finnhub_news_provider", fromlist=["fetch_company_news_with_retry"]).fetch_company_news_with_retry(
                api_key="test_key",
                symbol="AAPL",
                max_retries=2,
                fallback_days=1,
            )

            assert result == []
            assert not fallback_used
            # 1 initial + 2 retries on today + 6 fallback days * 3 retries each = 2 + 18 = 20
            assert mock_get.call_count == 21
