"""AI agent analysis module.

Provides AI-powered analysis of news data using a local LM Studio instance.
Extracts active sectors, catalysts, and operation recommendations.
"""

import dataclasses
from typing import Any, Optional

import httpx


@dataclasses.dataclass
class Catalyst:
    """A catalyst identified from news analysis."""

    type: str  # "product_launch", "regulatory_approval", "merger", "earnings", "patent", "other"
    description: str
    impact: str  # "positive", "negative", "neutral"
    stocks: list[str]


@dataclasses.dataclass
class OperationRecommendation:
    """An operation recommendation from the AI agent."""

    symbol: str
    direction: str  # "buy", "sell", or "short"
    confidence: float  # 0.0-1.0
    reasoning: str
    catalyst: Optional[str] = None


@dataclasses.dataclass
class ActiveSector:
    """An active sector identified by the AI agent."""

    sector: str
    stocks: list[str]
    direction: str  # "buy", "sell", or "short"
    confidence: float
    reasoning: str
    catalysts: Optional[list[Catalyst]] = None


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

    def analyze_news_with_catalysts(
        self,
        news_items: list[dict[str, Any]],
        company_news: list[dict[str, Any]],
        target_category: str,
    ) -> tuple[list[ActiveSector], list[Catalyst], list[OperationRecommendation]]:
        """Analyze news to identify active sectors, catalysts, and operations.

        Combines Alpha Vantage news with Finnhub company news for deeper analysis.

        Args:
            news_items: List of Alpha Vantage news items.
            company_news: List of Finnhub company news items.
            target_category: The target news category.

        Returns:
            Tuple of (active_sectors, catalysts, operation_recommendations).
        """
        if not news_items and not company_news:
            return [], [], []

        prompt = self._build_enhanced_analysis_prompt(news_items, company_news, target_category)

        response = httpx.post(
            f"{self.base_url}/chat/completions",
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": "You are a stock market analyst. Analyze news data to identify active sectors, catalysts, and recommend specific buy/sell/short operations with confidence scores."},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.1,
            },
        )
        response.raise_for_status()
        data = response.json()

        content = data["choices"][0]["message"]["content"]
        return self._parse_enhanced_analysis(content)

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

    def _build_enhanced_analysis_prompt(
        self,
        news_items: list[dict[str, Any]],
        company_news: list[dict[str, Any]],
        target_category: str,
    ) -> str:
        """Build an enhanced analysis prompt with catalyst extraction.

        Args:
            news_items: List of Alpha Vantage news items.
            company_news: List of Finnhub company news items.
            target_category: The target news category.

        Returns:
            The enhanced analysis prompt.
        """
        prompt = f"Analyze the following {target_category} news and company news to identify active sectors, catalysts, and specific operation recommendations.\n\n"

        if news_items:
            prompt += "=== General News ===\n\n"
            for i, item in enumerate(news_items):
                prompt += f"News {i + 1}:\n"
                prompt += f"  Headline: {item.get('headline', '')}\n"
                prompt += f"  Body: {item.get('body', '')}\n"
                prompt += f"  Categories: {', '.join(item.get('categories', []))}\n"
                prompt += f"  Sentiment: {item.get('sentiment', 'unknown')}\n"
                prompt += f"  Source: {item.get('source', '')}\n"
                prompt += f"  Time: {item.get('time_published', '')}\n\n"

        if company_news:
            prompt += "=== Company News ===\n\n"
            for i, item in enumerate(company_news):
                prompt += f"Company News {i + 1}:\n"
                prompt += f"  Headline: {item.get('headline', '')}\n"
                prompt += f"  Summary: {item.get('summary', '')}\n"
                prompt += f"  Source: {item.get('source', '')}\n"
                prompt += f"  Symbols: {', '.join(item.get('symbols', []))}\n"
                prompt += f"  Related: {', '.join(item.get('related', []))}\n"
                prompt += f"  Time: {item.get('time_published', '')}\n\n"

        prompt += """Please respond in JSON format with the following structure:
{
    "active_sectors": [
        {
            "sector": "sector name",
            "stocks": ["stock1", "stock2", ...],
            "direction": "buy" | "sell" | "short",
            "confidence": 0.0-1.0,
            "reasoning": "explanation",
            "catalysts": [
                {
                    "type": "product_launch" | "regulatory_approval" | "merger" | "earnings" | "patent" | "other",
                    "description": "description of the catalyst",
                    "impact": "positive" | "negative" | "neutral",
                    "stocks": ["affected stocks"]
                }
            ]
        }
    ],
    "catalysts": [
        {
            "type": "product_launch" | "regulatory_approval" | "merger" | "earnings" | "patent" | "other",
            "description": "description",
            "impact": "positive" | "negative" | "neutral",
            "stocks": ["affected stocks"]
        }
    ],
    "operations": [
        {
            "symbol": "stock symbol",
            "direction": "buy" | "sell" | "short",
            "confidence": 0.0-1.0,
            "reasoning": "explanation",
            "catalyst": "catalyst description"
        }
    ]
}

Guidelines:
1. Extract all catalysts: product launches, regulatory approvals, mergers, earnings, patents
2. For each active sector, identify the key catalysts driving activity
3. Recommend specific buy/sell/short operations with confidence scores
4. Confidence scores should reflect certainty (0.0 = no confidence, 1.0 = very confident)
5. Only recommend operations when there is a clear catalyst and sufficient evidence
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
                    catalysts=None,
                )
            )

        return active_sectors

    def _parse_enhanced_analysis(self, content: str) -> tuple[list[ActiveSector], list[Catalyst], list[OperationRecommendation]]:
        """Parse the enhanced AI agent response.

        Args:
            content: The AI agent's response content.

        Returns:
            Tuple of (active_sectors, catalysts, operation_recommendations).
        """
        import json

        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            return [], [], []

        # Parse active sectors
        sectors_data = data.get("active_sectors", [])
        active_sectors = []
        for sector_data in sectors_data:
            catalysts_raw = sector_data.get("catalysts", [])
            catalysts = []
            for cat in catalysts_raw:
                catalysts.append(
                    Catalyst(
                        type=cat.get("type", "other"),
                        description=cat.get("description", ""),
                        impact=cat.get("impact", "neutral"),
                        stocks=cat.get("stocks", []),
                    )
                )

            active_sectors.append(
                ActiveSector(
                    sector=sector_data.get("sector", ""),
                    stocks=sector_data.get("stocks", []),
                    direction=sector_data.get("direction", "buy"),
                    confidence=sector_data.get("confidence", 0.0),
                    reasoning=sector_data.get("reasoning", ""),
                    catalysts=catalysts if catalysts else None,
                )
            )

        # Parse standalone catalysts
        catalysts_raw = data.get("catalysts", [])
        catalysts = []
        for cat in catalysts_raw:
            catalysts.append(
                Catalyst(
                    type=cat.get("type", "other"),
                    description=cat.get("description", ""),
                    impact=cat.get("impact", "neutral"),
                    stocks=cat.get("stocks", []),
                )
            )

        # Parse operations
        ops_raw = data.get("operations", [])
        operations = []
        for op in ops_raw:
            operations.append(
                OperationRecommendation(
                    symbol=op.get("symbol", ""),
                    direction=op.get("direction", "buy"),
                    confidence=op.get("confidence", 0.0),
                    reasoning=op.get("reasoning", ""),
                    catalyst=op.get("catalyst"),
                )
            )

        return active_sectors, catalysts, operations


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
