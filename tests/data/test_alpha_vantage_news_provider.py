"""Tests for the AlphaVantageNewsProvider module."""

from unittest.mock import MagicMock, patch

import pytest

from stock_market_expert.data.alpha_vantage_news_provider import (
    AlphaVantageNewsProvider,
    NewsItem,
    Topic,
    TickerSentiment,
)


class TestAlphaVantageNewsProvider:
    """Tests for the AlphaVantageNewsProvider class."""

    def test_fetch_news_returns_parsed_items(self):
        """Fetching news should return parsed NewsItem objects."""
        mock_response = {
            "feed": [
                {
                    "title": "Test Headline",
                    "summary": "Test summary content",
                    "categories": ["technology"],
                    "source": "Test Source",
                    "time_published": "20260115T100000",
                    "url": "https://example.com/test",
                    "overall_sentiment_score": 0.25,
                    "overall_sentiment_label": "Somewhat-Bullish",
                    "topics": [
                        {"topic": "earnings", "relevance_score": "0.95"},
                    ],
                    "ticker_sentiment": [
                        {
                            "ticker": "AAPL",
                            "relevance_score": "0.80",
                            "ticker_sentiment_score": "0.30",
                            "ticker_sentiment_label": "Somewhat-Bullish",
                        }
                    ],
                    "banner_image": "https://example.com/banner.jpg",
                    "authors": ["John Doe", "Jane Smith"],
                    "category_within_source": "Technology",
                    "source_domain": "example.com",
                }
            ]
        }

        with patch("httpx.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = mock_response
            mock_get.return_value = mock_resp

            provider = AlphaVantageNewsProvider(api_key="test_key")
            result = provider.fetch_news(category="technology")

            assert len(result) == 1
            assert isinstance(result[0], NewsItem)
            assert result[0].headline == "Test Headline"
            assert result[0].summary == "Test summary content"
            assert result[0].categories == ["technology"]
            assert result[0].source == "Test Source"
            assert result[0].time_published == "20260115T100000"
            assert result[0].url == "https://example.com/test"
            assert result[0].overall_sentiment_score == 0.25
            assert result[0].overall_sentiment_label == "Somewhat-Bullish"
            assert len(result[0].topics) == 1
            assert result[0].topics[0].topic == "earnings"
            assert result[0].topics[0].relevance_score == 0.95
            assert len(result[0].ticker_sentiment) == 1
            assert result[0].ticker_sentiment[0].ticker == "AAPL"
            assert result[0].ticker_sentiment[0].ticker_sentiment_score == 0.30
            assert result[0].banner_image == "https://example.com/banner.jpg"
            assert result[0].authors == ["John Doe", "Jane Smith"]
            assert result[0].category_within_source == "Technology"
            assert result[0].source_domain == "example.com"

    def test_fetch_news_handles_empty_response(self):
        """Fetching news with no results should return an empty list."""
        mock_response = {"feed": []}

        with patch("httpx.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = mock_response
            mock_get.return_value = mock_resp

            provider = AlphaVantageNewsProvider(api_key="test_key")
            result = provider.fetch_news(category="technology")

            assert result == []

    def test_fetch_news_handles_null_banner_image(self):
        """banner_image can be null and should be handled gracefully."""
        mock_response = {
            "feed": [
                {
                    "title": "Test Headline",
                    "summary": "Test summary",
                    "categories": ["technology"],
                    "source": "Test Source",
                    "time_published": "20260115T100000",
                    "url": "https://example.com/test",
                    "overall_sentiment_score": 0.1,
                    "overall_sentiment_label": "Neutral",
                    "topics": [],
                    "ticker_sentiment": [],
                    "banner_image": None,
                    "authors": [],
                    "category_within_source": None,
                    "source_domain": None,
                }
            ]
        }

        with patch("httpx.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = mock_response
            mock_get.return_value = mock_resp

            provider = AlphaVantageNewsProvider(api_key="test_key")
            result = provider.fetch_news(category="technology")

            assert len(result) == 1
            assert result[0].banner_image is None
            assert result[0].authors == []
            assert result[0].category_within_source is None
            assert result[0].source_domain is None

    def test_fetch_news_handles_empty_authors_array(self):
        """authors can be an empty array and should be handled gracefully."""
        mock_response = {
            "feed": [
                {
                    "title": "Test Headline",
                    "summary": "Test summary",
                    "categories": ["technology"],
                    "source": "Test Source",
                    "time_published": "20260115T100000",
                    "url": "https://example.com/test",
                    "overall_sentiment_score": 0.1,
                    "overall_sentiment_label": "Neutral",
                    "topics": [],
                    "ticker_sentiment": [],
                    "banner_image": "https://example.com/banner.jpg",
                    "authors": [],
                }
            ]
        }

        with patch("httpx.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = mock_response
            mock_get.return_value = mock_resp

            provider = AlphaVantageNewsProvider(api_key="test_key")
            result = provider.fetch_news(category="technology")

            assert len(result) == 1
            assert result[0].authors == []

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
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = mock_response
            mock_get.return_value = mock_resp

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
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = mock_response
            mock_get.return_value = mock_resp

            provider = AlphaVantageNewsProvider(api_key="test_key")
            provider.fetch_news(category="technology", date="2024-01-15")

            mock_get.assert_called_once()
            call_args = mock_get.call_args
            assert call_args[1]["params"]["time_from"] == "2024-01-15T0000"
            assert call_args[1]["params"]["time_to"] == "2024-01-15T2359"


class TestFetchNewsWithRetry:
    """Tests for fetch_news_with_retry."""

    def test_returns_news_on_first_try(self):
        """Should return news on the first successful try."""
        mock_response = {
            "feed": [
                {
                    "title": "Test Headline",
                    "summary": "Test summary",
                    "categories": ["technology"],
                    "source": "Test Source",
                    "time_published": "20260115T100000",
                    "overall_sentiment_score": 0.2,
                    "overall_sentiment_label": "Somewhat-Bullish",
                    "topics": [],
                    "ticker_sentiment": [],
                    "banner_image": None,
                    "authors": [],
                }
            ]
        }

        with patch("httpx.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = mock_response
            mock_get.return_value = mock_resp

            result, fallback_used = __import__(
                "stock_market_expert.data.alpha_vantage_news_provider",
                fromlist=["fetch_news_with_retry"],
            ).fetch_news_with_retry(
                api_key="test_key",
                category="technology",
                max_retries=3,
                fallback_days=1,
            )

            assert len(result) == 1
            assert not fallback_used
            assert result[0].headline == "Test Headline"
            assert result[0].summary == "Test summary"
            mock_get.assert_called_once()

    def test_returns_empty_on_failure(self):
        """Should return empty list when all retries fail."""
        with patch("httpx.get") as mock_get:
            mock_get.side_effect = Exception("API Error")

            result, fallback_used = __import__(
                "stock_market_expert.data.alpha_vantage_news_provider",
                fromlist=["fetch_news_with_retry"],
            ).fetch_news_with_retry(
                api_key="test_key",
                category="technology",
                max_retries=2,
                fallback_days=1,
            )

            assert result == []
            assert not fallback_used
            # 1 initial + 2 retries on today + 6 fallback days * 3 retries each
            assert mock_get.call_count == 21

    def test_falls_back_to_previous_day(self):
        """Should fall back to previous days when today has no news."""
        call_count = [0]

        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                mock_empty = MagicMock()
                mock_empty.status_code = 200
                mock_empty.json.return_value = {"feed": []}
                return mock_empty
            else:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {
                    "feed": [
                        {
                            "title": "Fallback Headline",
                            "summary": "Fallback summary",
                            "categories": ["technology"],
                            "source": "Test Source",
                            "time_published": "20260114T100000",
                            "overall_sentiment_score": 0.1,
                            "overall_sentiment_label": "Neutral",
                            "topics": [],
                            "ticker_sentiment": [],
                            "banner_image": None,
                            "authors": [],
                        }
                    ]
                }
                return mock_response

        with patch("httpx.get") as mock_get:
            mock_get.side_effect = side_effect

            result, fallback_used = __import__(
                "stock_market_expert.data.alpha_vantage_news_provider",
                fromlist=["fetch_news_with_retry"],
            ).fetch_news_with_retry(
                api_key="test_key",
                category="technology",
                max_retries=0,
                fallback_days=1,
            )

            assert len(result) == 1
            assert result[0].headline == "Fallback Headline"
            assert result[0].summary == "Fallback summary"
            assert fallback_used


class TestFetchNewsWithFallback:
    """Tests for fetch_news_with_fallback."""

    def test_returns_fallback_data_on_failure(self):
        """Should return fallback data when API fails."""
        fallback = [
            NewsItem(
                headline="Fallback Headline",
                summary="Fallback summary",
                categories=["technology"],
                source="Fallback Source",
                time_published="20260115T100000",
            )
        ]

        with patch("httpx.get") as mock_get:
            mock_get.side_effect = Exception("API Error")

            result, fallback_used = __import__(
                "stock_market_expert.data.alpha_vantage_news_provider",
                fromlist=["fetch_news_with_fallback"],
            ).fetch_news_with_fallback(
                api_key="test_key",
                category="technology",
                max_retries=1,
                fallback_data=fallback,
            )

            assert len(result) == 1
            assert result[0].headline == "Fallback Headline"
            assert result[0].summary == "Fallback summary"
            assert fallback_used

    def test_returns_empty_without_fallback(self):
        """Should return empty list when no fallback data provided."""
        with patch("httpx.get") as mock_get:
            mock_get.side_effect = Exception("API Error")

            result, fallback_used = __import__(
                "stock_market_expert.data.alpha_vantage_news_provider",
                fromlist=["fetch_news_with_fallback"],
            ).fetch_news_with_fallback(
                api_key="test_key",
                category="technology",
                max_retries=1,
                fallback_data=None,
            )

            assert result == []
            assert not fallback_used
