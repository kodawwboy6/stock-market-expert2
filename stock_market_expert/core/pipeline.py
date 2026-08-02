"""News pipeline module.

Orchestrates the full news analysis pipeline:
Alpha Vantage → Finnhub → AI agent → active sectors

This is Step 1 of the news pipeline: reduces the stock universe
and does not influence Step 2 scoring.
"""

import dataclasses
import logging
from datetime import date
from typing import Optional

from stock_market_expert.config.loader import load_config
from stock_market_expert.core.agent import (
    ActiveSector,
    Agent,
    Catalyst,
    OperationRecommendation,
)
from stock_market_expert.data.alpha_vantage_news_provider import (
    AlphaVantageNewsProvider,
    NewsItem,
    fetch_news_with_fallback,
    fetch_news_with_retry,
)
from stock_market_expert.data.finnhub_news_provider import (
    FinnhubNewsProvider,
    CompanyNews,
    fetch_company_news_with_retry,
)

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class NewsPipelineResult:
    """Result from the news pipeline analysis."""

    active_sectors: list[ActiveSector]
    catalysts: list[Catalyst]
    operations: list[OperationRecommendation]
    news_count: int
    company_news_count: int
    fallback_used: bool
    date_used: str


class NewsPipeline:
    """Orchestrates the news analysis pipeline.

    Step 1: Alpha Vantage → Finnhub → AI agent → active sectors
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        finnhub_api_key: Optional[str] = None,
        lm_studio_base_url: Optional[str] = None,
        lm_studio_model: Optional[str] = None,
        news_category: Optional[str] = None,
        max_news_items: Optional[int] = None,
        confidence_threshold: Optional[float] = None,
    ):
        """Initialize the news pipeline.

        Args:
            api_key: Alpha Vantage API key. Defaults to config.
            finnhub_api_key: Finnhub API key. Defaults to config.
            lm_studio_base_url: LM Studio API URL. Defaults to config.
            lm_studio_model: LM Studio model name. Defaults to config.
            news_category: News category to analyze. Defaults to NEWS_CATEGORY env var.
            max_news_items: Maximum news items to fetch. Defaults to NEWS_MAX_ITEMS env var.
            confidence_threshold: Minimum confidence for operations. Defaults to NEWS_CONFIDENCE_THRESHOLD env var.
        """
        cfg = load_config()

        self.alpha_vantage_key = api_key or cfg.alpha_vantage_api_key
        self.finnhub_key = finnhub_api_key or cfg.finnhub_api_key
        self.lm_studio_base_url = lm_studio_base_url or cfg.lm_studio_base_url
        self.lm_studio_model = lm_studio_model or cfg.lm_studio_model
        self.news_category = news_category or cfg.news_category
        self.max_news_items = max_news_items if max_news_items is not None else cfg.news_max_items
        self.confidence_threshold = confidence_threshold if confidence_threshold is not None else cfg.news_confidence_threshold

        self.agent = Agent(
            base_url=self.lm_studio_base_url,
            model=self.lm_studio_model,
        )

    def run(
        self,
        fallback_data: Optional[list[NewsItem]] = None,
    ) -> NewsPipelineResult:
        """Run the full news pipeline.

        Step 1: Fetch tech news from Alpha Vantage
        Step 2: Extract stock symbols and fetch company news from Finnhub
        Step 3: Run AI analysis on combined news
        Step 4: Return active sectors, catalysts, and operations

        Args:
            fallback_data: Static news data to use if Alpha Vantage fails.

        Returns:
            NewsPipelineResult with analysis results.
        """
        logger.info("=== Starting News Pipeline (Step 1) ===")
        logger.info(f"Category: {self.news_category}")

        # Step 1: Fetch news from Alpha Vantage
        logger.info("Step 1: Fetching news from Alpha Vantage...")
        news_items, news_fallback_used = self._fetch_news(fallback_data)
        logger.info(f"Fetched {len(news_items)} news items")

        if not news_items:
            logger.warning("No news items fetched. Returning empty result.")
            return NewsPipelineResult(
                active_sectors=[],
                catalysts=[],
                operations=[],
                news_count=0,
                company_news_count=0,
                fallback_used=news_fallback_used or bool(fallback_data),
                date_used=date.today().isoformat(),
            )

        # Step 2: Extract symbols and fetch company news from Finnhub
        logger.info("Step 2: Extracting symbols and fetching company news from Finnhub...")
        symbols = self._extract_symbols(news_items)
        logger.info(f"Extracted {len(symbols)} unique symbols: {symbols}")

        company_news_items = []
        company_fallback_used = False
        if symbols and self.finnhub_key:
            for symbol in symbols:
                company_news, company_fallback = self._fetch_company_news(symbol)
                company_news_items.extend(company_news)
                if company_fallback:
                    company_fallback_used = True

        if company_news_items:
            logger.info(f"Fetched {len(company_news_items)} company news items")

        # Step 3: Run AI analysis
        logger.info("Step 3: Running AI analysis...")
        active_sectors, catalysts, operations = self._analyze_news(
            news_items, company_news_items
        )
        logger.info(
            f"Analysis complete: {len(active_sectors)} sectors, "
            f"{len(catalysts)} catalysts, {len(operations)} operations"
        )

        return NewsPipelineResult(
            active_sectors=active_sectors,
            catalysts=catalysts,
            operations=operations,
            news_count=len(news_items),
            company_news_count=len(company_news_items),
            fallback_used=news_fallback_used or company_fallback_used or bool(fallback_data),
            date_used=date.today().isoformat(),
        )

    def _fetch_news(
        self,
        fallback_data: Optional[list[NewsItem]] = None,
    ) -> tuple[list[NewsItem], bool]:
        """Fetch news with fallback support.

        Args:
            fallback_data: Static news data to use if Alpha Vantage fails.

        Returns:
            Tuple of (news items, bool indicating if fallback was used).
        """
        if not self.alpha_vantage_key:
            logger.warning("Alpha Vantage API key not configured, returning fallback")
            if fallback_data:
                return fallback_data, True
            return [], True

        # Try with static fallback data first
        if fallback_data is not None:
            items, used = fetch_news_with_fallback(
                api_key=self.alpha_vantage_key,
                category=self.news_category,
                fallback_data=fallback_data,
            )
            return items, used or True

        items, fallback_used = fetch_news_with_retry(
            api_key=self.alpha_vantage_key,
            category=self.news_category,
        )
        return items, fallback_used

    def _extract_symbols(self, news_items: list[NewsItem]) -> list[str]:
        """Extract unique stock symbols from news items.

        Primary source: ticker_sentiment from the Alpha Vantage API.
        Fallback: heuristic scan of headlines for uppercase words.

        Args:
            news_items: List of news items.

        Returns:
            List of unique stock symbols.
        """
        symbols = set()

        for item in news_items:
            # Primary: use structured ticker_sentiment data from API
            for ts in item.ticker_sentiment:
                if ts.ticker:
                    symbols.add(ts.ticker)

            # Fallback: heuristic scan of headline for uppercase words (2-5 chars)
            for word in item.headline.split():
                word = word.strip(".,!?;:")
                if 2 <= len(word) <= 5 and word.isupper() and word.isalpha():
                    symbols.add(word)

        # Filter out common non-ticker words
        non_tickers = {
            "THE", "AND", "FOR", "NEW", "NOT", "BUT", "ALL", "HAS",
            "HOW", "WHO", "WHY", "THEY", "THIS", "THAT", "WITH", "FROM",
            "HAVE", "SAYS", "MORE", "OVER", "SAME", "WILL", "EACH",
            "MAKE", "LIKE", "JUST", "ONLY", "TODAY", "YEAR", "MANY",
            "GOOD", "FIRST", "LAST", "LONG", "GREAT", "LITTLE", "OWN",
            "OTHER",
        }
        symbols -= non_tickers

        # Limit to reasonable number of symbols
        return sorted(list(symbols))[:20]

    def _fetch_company_news(self, symbol: str) -> tuple[list[CompanyNews], bool]:
        """Fetch company news with retry and fallback.

        Returns:
            Tuple of (company news items, bool indicating if fallback was used).
        """
        if not self.finnhub_key:
            logger.warning(f"Finnhub API key not configured, skipping {symbol}")
            return [], False

        today = date.today().isoformat()
        items, fallback_used = fetch_company_news_with_retry(
            api_key=self.finnhub_key,
            symbol=symbol,
            date_from=today,
            date_to=today,
        )
        return items, fallback_used

    def _analyze_news(
        self,
        news_items: list[NewsItem],
        company_news_items: list[CompanyNews],
    ) -> tuple[list[ActiveSector], list[Catalyst], list[OperationRecommendation]]:
        """Run AI analysis on combined news.

        Args:
            news_items: Alpha Vantage news items.
            company_news_items: Finnhub company news items.

        Returns:
            Tuple of (active_sectors, catalysts, operations).
        """
        if not news_items:
            return [], [], []

        # Convert to dict format for the agent
        news_dicts = [
            {
                "headline": item.headline,
                "summary": item.summary,
                "categories": item.categories,
                "source": item.source,
                "time_published": item.time_published,
                "overall_sentiment_score": item.overall_sentiment_score,
                "overall_sentiment_label": item.overall_sentiment_label,
                "ticker_sentiment": [
                    {
                        "ticker": ts.ticker,
                        "relevance_score": ts.relevance_score,
                        "sentiment_score": ts.ticker_sentiment_score,
                        "sentiment_label": ts.ticker_sentiment_label,
                    }
                    for ts in item.ticker_sentiment
                ],
                "topics": [
                    {"topic": t.topic, "relevance_score": t.relevance_score}
                    for t in item.topics
                ],
            }
            for item in news_items
        ]

        company_dicts = [
            {
                "headline": item.headline,
                "summary": item.summary,
                "source": item.source,
                "symbols": item.symbols or [],
                "related": item.related or [],
                "time_published": item.time_published,
            }
            for item in company_news_items
        ]

        return self.agent.analyze_news_with_catalysts(
            news_items=news_dicts,
            company_news=company_dicts,
            target_category=self.news_category,
        )


def run_news_pipeline(
    category: str = "technology",
    api_key: Optional[str] = None,
    finnhub_api_key: Optional[str] = None,
    lm_studio_base_url: Optional[str] = None,
    lm_studio_model: Optional[str] = None,
) -> NewsPipelineResult:
    """Convenience function to run the news pipeline.

    Args:
        category: News category to analyze.
        api_key: Alpha Vantage API key.
        finnhub_api_key: Finnhub API key.
        lm_studio_base_url: LM Studio API URL.
        lm_studio_model: LM Studio model name.

    Returns:
        NewsPipelineResult with analysis results.
    """
    pipeline = NewsPipeline(
        api_key=api_key,
        finnhub_api_key=finnhub_api_key,
        lm_studio_base_url=lm_studio_base_url,
        lm_studio_model=lm_studio_model,
        news_category=category,
    )
    return pipeline.run()
