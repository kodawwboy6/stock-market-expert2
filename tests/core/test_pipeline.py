"""Tests for the news pipeline module."""

from unittest.mock import MagicMock, patch

import pytest

from stock_market_expert.core.pipeline import (
    NewsPipeline,
    NewsPipelineResult,
    run_news_pipeline,
)
from stock_market_expert.data.alpha_vantage_news_provider import NewsItem, TickerSentiment


class TestNewsPipeline:
    """Tests for the NewsPipeline class."""

    @patch("stock_market_expert.core.pipeline.load_config")
    def test_init_uses_config_defaults(self, mock_config):
        """Should use config defaults when no args provided."""
        mock_config.return_value = MagicMock(
            alpha_vantage_api_key="av_key",
            finnhub_api_key="fh_key",
            lm_studio_base_url="http://localhost:1234/v1",
            lm_studio_model="lms-7b",
        )

        pipeline = NewsPipeline(news_category="technology")

        assert pipeline.alpha_vantage_key == "av_key"
        assert pipeline.finnhub_key == "fh_key"
        assert pipeline.lm_studio_base_url == "http://localhost:1234/v1"
        assert pipeline.lm_studio_model == "lms-7b"
        assert pipeline.news_category == "technology"

    @patch("stock_market_expert.core.pipeline.load_config")
    @patch("stock_market_expert.core.pipeline.fetch_news_with_retry")
    @patch("stock_market_expert.core.pipeline.fetch_company_news_with_retry")
    @patch("stock_market_expert.core.pipeline.Agent")
    def test_run_returns_result(self, mock_agent_class, mock_finnhub, mock_fetch, mock_config):
        """Running the pipeline should return a NewsPipelineResult."""
        mock_config.return_value = MagicMock(
            alpha_vantage_api_key="av_key",
            finnhub_api_key="fh_key",
            lm_studio_base_url="http://localhost:1234/v1",
            lm_studio_model="lms-7b",
        )

        mock_fetch.return_value = (
            [
                NewsItem(
                    headline="AI Company Launches New Product",
                    summary="A leading AI company announced a breakthrough product.",
                    categories=["technology", "ai"],
                    source="Tech News",
                    time_published="2024-01-15T10:00:00Z",
                    overall_sentiment_score=0.5,
                    overall_sentiment_label="Somewhat-Bullish",
                    ticker_sentiment=[
                        TickerSentiment(ticker="AAPL", relevance_score=0.9, ticker_sentiment_score=0.5, ticker_sentiment_label="Bullish"),
                    ],
                )
            ],
            False,
        )
        mock_finnhub.return_value = (
            [
                MagicMock(headline="AAPL News", summary="Summary", source="Source",
                          symbols=["AAPL"], related=[], time_published="2024-01-15T11:00:00Z")
            ],
            False,
        )

        mock_agent = MagicMock()
        mock_agent.analyze_news_with_catalysts.return_value = (
            [MagicMock(sector="AI", stocks=["AAPL"], direction="buy", confidence=0.85, reasoning="test")],
            [MagicMock(type="product_launch", description="New product", impact="positive", stocks=["AAPL"])],
            [MagicMock(symbol="AAPL", direction="buy", confidence=0.85, reasoning="test", catalyst="New product")],
        )
        mock_agent_class.return_value = mock_agent

        pipeline = NewsPipeline(
            api_key="av_key",
            finnhub_api_key="fh_key",
            lm_studio_base_url="http://localhost:1234/v1",
            lm_studio_model="lms-7b",
            news_category="technology",
        )
        result = pipeline.run()

        assert isinstance(result, NewsPipelineResult)
        assert len(result.active_sectors) == 1
        assert len(result.catalysts) == 1
        assert len(result.operations) == 1
        assert result.news_count == 1
        assert result.company_news_count == 1

    @patch("stock_market_expert.core.pipeline.load_config")
    @patch("stock_market_expert.core.pipeline.fetch_news_with_retry")
    def test_run_handles_empty_news(self, mock_fetch, mock_config):
        """Should return empty result when no news is fetched."""
        mock_config.return_value = MagicMock(
            alpha_vantage_api_key="av_key",
            finnhub_api_key="fh_key",
            lm_studio_base_url="http://localhost:1234/v1",
            lm_studio_model="lms-7b",
        )
        mock_fetch.return_value = ([], False)

        pipeline = NewsPipeline(
            api_key="av_key",
            finnhub_api_key="fh_key",
            lm_studio_base_url="http://localhost:1234/v1",
            lm_studio_model="lms-7b",
            news_category="technology",
        )
        result = pipeline.run()

        assert result.active_sectors == []
        assert result.catalysts == []
        assert result.operations == []
        assert result.news_count == 0
        assert not result.fallback_used

    @patch("stock_market_expert.core.pipeline.load_config")
    def test_init_with_no_api_keys(self, mock_config):
        """Should handle missing API keys gracefully."""
        mock_config.return_value = MagicMock(
            alpha_vantage_api_key="",
            finnhub_api_key="",
            lm_studio_base_url="http://localhost:1234/v1",
            lm_studio_model="lms-7b",
        )

        pipeline = NewsPipeline()

        assert pipeline.alpha_vantage_key == ""
        assert pipeline.finnhub_key == ""

    def test_extract_symbols(self):
        """Should extract ticker symbols from news items."""
        pipeline = NewsPipeline(api_key="test", finnhub_api_key="test")

        news_items = [
            NewsItem(
                headline="AAPL Reports Strong Earnings",
                summary="Apple Inc. (AAPL) reported strong quarterly earnings, beating expectations.",
                categories=["technology", "earnings"],
                source="Tech News",
                time_published="2024-01-15T10:00:00Z",
                ticker_sentiment=[
                    TickerSentiment(ticker="AAPL", relevance_score=0.9, ticker_sentiment_score=0.5, ticker_sentiment_label="Somewhat-Bullish"),
                ],
            ),
            NewsItem(
                headline="NVDA Announces New AI Chip",
                summary="NVIDIA (NVDA) announced a new AI chip for data centers.",
                categories=["technology", "ai"],
                source="Industry News",
                time_published="2024-01-15T11:00:00Z",
                ticker_sentiment=[
                    TickerSentiment(ticker="NVDA", relevance_score=0.85, ticker_sentiment_score=0.7, ticker_sentiment_label="Bullish"),
                ],
            ),
        ]

        symbols = pipeline._extract_symbols(news_items)

        assert "AAPL" in symbols
        assert "NVDA" in symbols

    def test_extract_symbols_sorted_by_occurrence(self):
        """Should sort symbols by occurrence count descending."""
        pipeline = NewsPipeline(api_key="test", finnhub_api_key="test")

        news_items = [
            NewsItem(
                headline="AAPL and NVDA both report earnings",
                summary="AAPL earnings beat expectations. NVDA also strong.",
                categories=["technology"],
                source="Tech News",
                time_published="2024-01-15T10:00:00Z",
                ticker_sentiment=[
                    TickerSentiment(ticker="AAPL", relevance_score=0.9, ticker_sentiment_score=0.5, ticker_sentiment_label="Bullish"),
                    TickerSentiment(ticker="NVDA", relevance_score=0.8, ticker_sentiment_score=0.6, ticker_sentiment_label="Bullish"),
                ],
            ),
            NewsItem(
                headline="AAPL launches new product",
                summary="AAPL announced a new product line.",
                categories=["technology"],
                source="Tech News",
                time_published="2024-01-15T11:00:00Z",
                ticker_sentiment=[
                    TickerSentiment(ticker="AAPL", relevance_score=0.85, ticker_sentiment_score=0.7, ticker_sentiment_label="Bullish"),
                ],
            ),
            NewsItem(
                headline="NVDA AI chip update",
                summary="NVDA continues to lead in AI chips.",
                categories=["technology"],
                source="Industry News",
                time_published="2024-01-15T12:00:00Z",
                ticker_sentiment=[
                    TickerSentiment(ticker="NVDA", relevance_score=0.75, ticker_sentiment_score=0.4, ticker_sentiment_label="Somewhat-Bullish"),
                ],
            ),
        ]

        symbols = pipeline._extract_symbols(news_items)

        # AAPL appears 3 times, NVDA appears 2 times
        assert symbols.index("AAPL") < symbols.index("NVDA")

    def test_extract_symbols_filters_non_tickers(self):
        """Should filter out common non-ticker words."""
        pipeline = NewsPipeline(api_key="test", finnhub_api_key="test")

        news_items = [
            NewsItem(
                headline="THE NEW YEAR EACH HAS GOOD NEWS",
                summary="ALL OVER THE WORLD SAME YEAR",
                categories=["technology"],
                source="Test Source",
                time_published="2024-01-15T10:00:00Z",
            ),
        ]

        symbols = pipeline._extract_symbols(news_items)

        # Common words should be filtered out
        assert "THE" not in symbols
        assert "NEW" not in symbols
        assert "EACH" not in symbols
        assert "HAS" not in symbols
        assert "GOOD" not in symbols
        assert "ALL" not in symbols

    def test_extract_symbols_limits_to_20(self):
        """Should limit extracted symbols to 20."""
        pipeline = NewsPipeline(api_key="test", finnhub_api_key="test")

        # Create news with many potential symbols
        symbols_in_text = [f"SYMBOL{i:02d}" for i in range(30)]
        headline = " ".join(symbols_in_text)

        news_items = [
            NewsItem(
                headline=headline,
                summary="",
                categories=["technology"],
                source="Test Source",
                time_published="2024-01-15T10:00:00Z",
            ),
        ]

        extracted = pipeline._extract_symbols(news_items)
        assert len(extracted) <= 20

    def test_extract_symbols_configurable_limit(self):
        """Should respect configurable news_symbols_limit."""
        pipeline = NewsPipeline(
            api_key="test",
            finnhub_api_key="test",
            news_symbols_limit=5,
        )

        tickers = ["AAPL", "NVDA", "MSFT", "GOOGL", "AMZN", "TSLA", "META"]
        news_items = [
            NewsItem(
                headline="Tech stocks report earnings",
                summary="All tech stocks report earnings.",
                categories=["technology"],
                source="Test Source",
                time_published="2024-01-15T10:00:00Z",
                ticker_sentiment=[
                    TickerSentiment(ticker=t, relevance_score=0.8, ticker_sentiment_score=0.5, ticker_sentiment_label="Bullish")
                    for t in tickers
                ],
            ),
        ]

        extracted = pipeline._extract_symbols(news_items)
        assert len(extracted) == 5

    def test_extract_symbols_default_limit_preserves_behavior(self):
        """Default limit of 20 should preserve existing behavior."""
        pipeline = NewsPipeline(api_key="test", finnhub_api_key="test")

        assert pipeline.news_symbols_limit == 20

    @patch("stock_market_expert.core.pipeline.load_config")
    @patch("stock_market_expert.core.pipeline.fetch_news_with_retry")
    def test_run_tracks_fallback_used_on_retry_fallback(self, mock_fetch, mock_config):
        """Should set fallback_used=True when retry falls back to previous days."""
        mock_config.return_value = MagicMock(
            alpha_vantage_api_key="av_key",
            finnhub_api_key="fh_key",
            lm_studio_base_url="http://localhost:1234/v1",
            lm_studio_model="lms-7b",
        )
        mock_fetch.return_value = ([], True)  # simulate fallback was used

        pipeline = NewsPipeline(
            api_key="av_key",
            finnhub_api_key="fh_key",
            lm_studio_base_url="http://localhost:1234/v1",
            lm_studio_model="lms-7b",
            news_category="technology",
        )
        result = pipeline.run()

        assert result.fallback_used is True

    @patch("stock_market_expert.core.pipeline.load_config")
    @patch("stock_market_expert.core.pipeline.fetch_news_with_fallback")
    def test_run_tracks_fallback_used_on_static_fallback(self, mock_fetch, mock_config):
        """Should set fallback_used=True when static fallback_data is used."""
        mock_config.return_value = MagicMock(
            alpha_vantage_api_key="av_key",
            finnhub_api_key="fh_key",
            lm_studio_base_url="http://localhost:1234/v1",
            lm_studio_model="lms-7b",
        )
        mock_fetch.return_value = ([], True)

        pipeline = NewsPipeline(
            api_key="av_key",
            finnhub_api_key="fh_key",
            lm_studio_base_url="http://localhost:1234/v1",
            lm_studio_model="lms-7b",
            news_category="technology",
        )
        fallback_data = [
            NewsItem(
                headline="Fallback News",
                summary="Fallback summary",
                categories=["technology"],
                source="Fallback",
                time_published="2024-01-15T10:00:00Z",
            )
        ]
        result = pipeline.run(fallback_data=fallback_data)

        assert result.fallback_used is True

    @patch("stock_market_expert.core.pipeline.load_config")
    @patch("stock_market_expert.core.pipeline.fetch_news_with_retry")
    @patch("stock_market_expert.core.pipeline.Agent")
    def test_run_no_fallback_when_api_succeeds(self, mock_agent_class, mock_fetch, mock_config):
        """Should set fallback_used=False when API succeeds."""
        mock_config.return_value = MagicMock(
            alpha_vantage_api_key="av_key",
            finnhub_api_key="fh_key",
            lm_studio_base_url="http://localhost:1234/v1",
            lm_studio_model="lms-7b",
        )
        mock_fetch.return_value = (
            [
                NewsItem(
                    headline="Real News",
                    summary="Real summary",
                    categories=["technology"],
                    source="Real",
                    time_published="2024-01-15T10:00:00Z",
                )
            ],
            False,
        )
        mock_agent = MagicMock()
        mock_agent.analyze_news_with_catalysts.return_value = ([], [], [])
        mock_agent_class.return_value = mock_agent

        pipeline = NewsPipeline(
            api_key="av_key",
            finnhub_api_key="fh_key",
            lm_studio_base_url="http://localhost:1234/v1",
            lm_studio_model="lms-7b",
            news_category="technology",
        )
        result = pipeline.run()

        assert result.fallback_used is False

class TestRunNewsPipeline:
    """Tests for the run_news_pipeline convenience function."""

    @patch("stock_market_expert.core.pipeline.NewsPipeline")
    def test_uses_news_pipeline(self, mock_pipeline_class):
        """Should create and use a NewsPipeline instance."""
        mock_result = MagicMock()
        mock_pipeline_class.return_value.run.return_value = mock_result

        result = run_news_pipeline(category="technology")

        mock_pipeline_class.assert_called_once()
        mock_pipeline_class.return_value.run.assert_called_once()
        assert result is mock_result
