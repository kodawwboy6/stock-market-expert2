"""Tests for the AI agent analysis module."""

from unittest.mock import MagicMock, patch

import pytest

from stock_market_expert.core.agent import (
    Agent,
    ActiveSector,
    analyze_news_for_active_sectors,
)


class TestAgent:
    """Tests for the Agent class."""

    def test_analyze_news_for_active_sectors(self):
        """Analyzing news should return active sectors with operation recommendations."""
        mock_news = [
            {
                "headline": "AI Company Launches New Product",
                "body": "A leading AI company announced a breakthrough product.",
                "categories": ["technology", "ai"],
                "source": "Tech News",
                "time_published": "2024-01-15T10:00:00Z",
                "sentiment": "positive",
                "url": "https://example.com/test1",
            },
            {
                "headline": "Semiconductor Shortage Eases",
                "body": "The semiconductor shortage is finally easing.",
                "categories": ["technology", "semiconductors"],
                "source": "Industry News",
                "time_published": "2024-01-15T11:00:00Z",
                "sentiment": "positive",
                "url": "https://example.com/test2",
            },
        ]

        # Mock LLM response in OpenAI-compatible format
        mock_llm_response = {
            "choices": [
                {
                    "message": {
                        "content": '''{
                            "active_sectors": [
                                {
                                    "sector": "AI",
                                    "stocks": ["NVDA", "AMD", "AVGO"],
                                    "direction": "buy",
                                    "confidence": 0.85,
                                    "reasoning": "Positive news + catalyst"
                                },
                                {
                                    "sector": "Semiconductors",
                                    "stocks": ["TSM", "QCOM", "MU"],
                                    "direction": "buy",
                                    "confidence": 0.75,
                                    "reasoning": "Positive news + easing shortage"
                                }
                            ]
                        }'''
                    }
                }
            ]
        }

        with patch("httpx.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200, json=MagicMock(return_value=mock_llm_response))

            agent = Agent(base_url="http://localhost:1234/v1", model="lms-7b")
            result = agent.analyze_news_for_active_sectors(mock_news, "technology")

            assert len(result) == 2
            assert isinstance(result[0], ActiveSector)
            assert result[0].sector == "AI"
            assert result[0].stocks == ["NVDA", "AMD", "AVGO"]
            assert result[0].direction == "buy"
            assert result[0].confidence == 0.85

    def test_analyze_news_handles_empty_news(self):
        """Analyzing empty news should return an empty list."""
        agent = Agent(base_url="http://localhost:1234/v1", model="lms-7b")
        result = agent.analyze_news_for_active_sectors([], "technology")

        assert result == []

    def test_analyze_news_raises_on_api_error(self):
        """Analyzing news with an API error should raise an exception."""
        mock_news = [{"headline": "Test", "body": "Test", "categories": ["technology"]}]

        with patch("httpx.post") as mock_post:
            mock_post.side_effect = Exception("API Error")

            agent = Agent(base_url="http://localhost:1234/v1", model="lms-7b")

            with pytest.raises(Exception, match="API Error"):
                agent.analyze_news_for_active_sectors(mock_news, "technology")


class TestAnalyzeNewsForActiveSectors:
    """Tests for the module-level analyze_news_for_active_sectors function."""

    def test_analyze_news_for_active_sectors_uses_default_agent(self):
        """The module-level function should use the default agent."""
        mock_news = [{"headline": "Test", "body": "Test", "categories": ["technology"]}]
        mock_llm_response = {
            "choices": [
                {
                    "message": {
                        "content": '{"active_sectors": []}'
                    }
                }
            ]
        }

        with patch("httpx.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200, json=MagicMock(return_value=mock_llm_response))

            result = analyze_news_for_active_sectors(mock_news, "technology")

            assert result == []


class TestAgentEnhancedAnalysis:
    """Tests for the Agent's enhanced analysis with catalysts."""

    def test_analyze_news_with_catalysts(self):
        """Enhanced analysis should return sectors, catalysts, and operations."""
        mock_news = [
            {"headline": "AI Company Launches New Product", "body": "Test", "categories": ["technology", "ai"], "source": "Tech News", "time_published": "2024-01-15T10:00:00Z", "sentiment": "positive"},
        ]
        mock_company_news = [
            {"headline": "AAPL News", "summary": "Summary", "source": "Source", "symbols": ["AAPL"], "related": [], "time_published": "2024-01-15T11:00:00Z"},
        ]

        mock_llm_response = {
            "choices": [
                {
                    "message": {
                        "content": '''{
                            "active_sectors": [
                                {
                                    "sector": "AI",
                                    "stocks": ["AAPL"],
                                    "direction": "buy",
                                    "confidence": 0.85,
                                    "reasoning": "Positive catalyst",
                                    "catalysts": [
                                        {
                                            "type": "product_launch",
                                            "description": "New product launch",
                                            "impact": "positive",
                                            "stocks": ["AAPL"]
                                        }
                                    ]
                                }
                            ],
                            "catalysts": [
                                {
                                    "type": "product_launch",
                                    "description": "New product launch",
                                    "impact": "positive",
                                    "stocks": ["AAPL"]
                                }
                            ],
                            "operations": [
                                {
                                    "symbol": "AAPL",
                                    "direction": "buy",
                                    "confidence": 0.85,
                                    "reasoning": "Strong catalyst",
                                    "catalyst": "New product launch"
                                }
                            ]
                        }'''
                    }
                }
            ]
        }

        with patch("httpx.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200, json=MagicMock(return_value=mock_llm_response))

            agent = Agent(base_url="http://localhost:1234/v1", model="lms-7b")
            sectors, catalysts, operations = agent.analyze_news_with_catalysts(
                news_items=mock_news,
                company_news=mock_company_news,
                target_category="technology",
            )

            assert len(sectors) == 1
            assert sectors[0].sector == "AI"
            assert sectors[0].catalysts is not None
            assert len(sectors[0].catalysts) == 1
            assert sectors[0].catalysts[0].type == "product_launch"

            assert len(catalysts) == 1
            assert catalysts[0].type == "product_launch"

            assert len(operations) == 1
            assert operations[0].symbol == "AAPL"
            assert operations[0].direction == "buy"
            assert operations[0].confidence == 0.85

    def test_analyze_news_with_catalysts_handles_empty_input(self):
        """Enhanced analysis with empty input should return empty lists."""
        agent = Agent(base_url="http://localhost:1234/v1", model="lms-7b")
        sectors, catalysts, operations = agent.analyze_news_with_catalysts(
            news_items=[],
            company_news=[],
            target_category="technology",
        )

        assert sectors == []
        assert catalysts == []
        assert operations == []

    def test_analyze_news_with_catalysts_handles_api_error(self):
        """Enhanced analysis with an API error should raise an exception."""
        mock_news = [{"headline": "Test", "body": "Test", "categories": ["technology"]}]
        mock_company_news = [{"headline": "Test", "summary": "Test", "source": "Source", "symbols": ["AAPL"], "related": [], "time_published": "2024-01-15T10:00:00Z"}]

        with patch("httpx.post") as mock_post:
            mock_post.side_effect = Exception("API Error")

            agent = Agent(base_url="http://localhost:1234/v1", model="lms-7b")

            with pytest.raises(Exception, match="API Error"):
                agent.analyze_news_with_catalysts(
                    news_items=mock_news,
                    company_news=mock_company_news,
                    target_category="technology",
                )

    def test_analyze_news_with_catalysts_handles_invalid_json(self):
        """Enhanced analysis with invalid JSON should return empty lists."""
        mock_news = [{"headline": "Test", "body": "Test", "categories": ["technology"]}]
        mock_company_news = []

        mock_llm_response = {
            "choices": [
                {"message": {"content": "not valid json"}}
            ]
        }

        with patch("httpx.post") as mock_post:
            mock_post.return_value = MagicMock(status_code=200, json=MagicMock(return_value=mock_llm_response))

            agent = Agent(base_url="http://localhost:1234/v1", model="lms-7b")
            sectors, catalysts, operations = agent.analyze_news_with_catalysts(
                news_items=mock_news,
                company_news=mock_company_news,
                target_category="technology",
            )

            assert sectors == []
            assert catalysts == []
            assert operations == []
