"""AI agent analysis module.

Provides AI-powered analysis of news data using a local LM Studio instance.
"""

import dataclasses
from typing import Any, Optional

import httpx


@dataclasses.dataclass
class ActiveSector:
    """An active sector identified by the AI agent."""

    sector: str
    stocks: list[str]
    direction: str  # "buy", "sell", or "short"
    confidence: float
    reasoning: str


class Agent:
    """AI agent for news analysis using LM Studio.

    Analyzes news data to identify active sectors and operation recommendations.
    """

    def __init__(self, base_url: str = "http://localhost:1234/v1", model: str = "lms-7b"):
        """Initialize the agent.

        Args:
            base_url: LM Studio API base URL.
            model: LM Studio model name.
        """
        self.base_url = base_url
        self.model = model

    def analyze_news_for_active_sectors(
        self,
        news_items: list[dict[str, Any]],
        target_category: str,
    ) -> list[ActiveSector]:
        """Analyze news to identify active sectors.

        Args:
            news_items: List of news items to analyze.
            target_category: The target news category (e.g., "technology").

        Returns:
            List of ActiveSector objects.

        Raises:
            Exception: If the AI API request fails.
        """
        if not news_items:
            return []

        # Build the prompt for the AI agent
        prompt = self._build_analysis_prompt(news_items, target_category)

        # Call the LM Studio API
        response = httpx.post(
            f"{self.base_url}/chat/completions",
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": "You are a stock market analyst. Analyze news data to identify active sectors and recommend operations."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.1,
            },
        )
        response.raise_for_status()
        data = response.json()

        # Parse the response
        content = data["choices"][0]["message"]["content"]
        return self._parse_active_sectors(content)

    def _build_analysis_prompt(self, news_items: list[dict[str, Any]], target_category: str) -> str:
        """Build the analysis prompt for the AI agent.

        Args:
            news_items: List of news items to analyze.
            target_category: The target news category.

        Returns:
            The analysis prompt.
        """
        prompt = f"Analyze the following {target_category} news to identify active sectors.\n\n"

        for i, item in enumerate(news_items):
            prompt += f"News {i + 1}:\n"
            prompt += f"  Headline: {item.get('headline', '')}\n"
            prompt += f"  Body: {item.get('body', '')}\n"
            prompt += f"  Categories: {', '.join(item.get('categories', []))}\n"
            prompt += f"  Sentiment: {item.get('sentiment', 'unknown')}\n"
            prompt += f"  Source: {item.get('source', '')}\n"
            prompt += f"  Time: {item.get('time_published', '')}\n\n"

        prompt += """Please respond in JSON format with the following structure:
{
    "active_sectors": [
        {
            "sector": "sector name",
            "stocks": ["stock1", "stock2", ...],
            "direction": "buy" | "sell" | "short",
            "confidence": 0.0-1.0,
            "reasoning": "explanation"
        },
        ...
    ]
}

Guidelines for analysis:
1. Identify sectors with unusual news activity (volume, sentiment, catalysts)
2. For each sector, recommend buy/sell/short operations based on:
   - News volume increase (relative to normal)
   - Sentiment (positive/negative)
   - Catalysts (product launches, regulatory approvals, mergers, earnings, patents)
3. Confidence score should reflect certainty in the recommendation (0.0-1.0)
4. Reasoning should explain the basis for the recommendation
"""

        return prompt

    def _parse_active_sectors(self, content: str) -> list[ActiveSector]:
        """Parse the AI agent's response into ActiveSector objects.

        Args:
            content: The AI agent's response content.

        Returns:
            List of ActiveSector objects.
        """
        import json

        try:
            data = json.loads(content)
            sectors_data = data.get("active_sectors", [])
        except json.JSONDecodeError:
            # If JSON parsing fails, return an empty list
            return []

        active_sectors = []
        for sector_data in sectors_data:
            active_sectors.append(
                ActiveSector(
                    sector=sector_data.get("sector", ""),
                    stocks=sector_data.get("stocks", []),
                    direction=sector_data.get("direction", "buy"),
                    confidence=sector_data.get("confidence", 0.0),
                    reasoning=sector_data.get("reasoning", ""),
                )
            )

        return active_sectors


# Module-level convenience function
def analyze_news_for_active_sectors(
    news_items: list[dict[str, Any]],
    target_category: str,
    base_url: str = "http://localhost:1234/v1",
    model: str = "lms-7b",
) -> list[ActiveSector]:
    """Module-level convenience function for analyzing news.

    Args:
        news_items: List of news items to analyze.
        target_category: The target news category.
        base_url: LM Studio API base URL.
        model: LM Studio model name.

    Returns:
        List of ActiveSector objects.
    """
    agent = Agent(base_url=base_url, model=model)
    return agent.analyze_news_for_active_sectors(news_items, target_category)
