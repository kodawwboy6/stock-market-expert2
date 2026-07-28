"""Signal engine for technical analysis and signal generation.

Orchestrates data fetching, indicator computation, weighted aggregation,
and signal deduplication to produce buy/sell signals.
"""

import dataclasses
import os
from datetime import datetime, timezone
from typing import Any, Optional

from stock_market_expert.analysis.aggregation import AggregatedSignal, weighted_aggregate
from stock_market_expert.analysis.macd import MacdResult, compute_macd
from stock_market_expert.analysis.roc import RocResult, compute_roc
from stock_market_expert.analysis.volume import VolumeResult, compute_volume_score
from stock_market_expert.data.alpaca_provider import AlpacaProvider
from stock_market_expert.data.twelve_data_provider import TwelveDataProvider


@dataclasses.dataclass
class TechnicalSignal:
    """A buy/sell signal generated from technical analysis.

    Attributes:
        symbol: Stock ticker symbol.
        direction: "buy" or "sell".
        confidence: Independent confidence score from technical analysis (0.0–1.0).
        score: Weighted aggregation score.
        reasoning: Explanation of the signal basis.
        timestamp: When the signal was generated.
    """

    symbol: str
    direction: str
    confidence: float
    score: float
    reasoning: str
    timestamp: str = dataclasses.field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class SignalEngine:
    """Technical signal generation engine.

    Fetches historical and real-time data, computes MACD/ROC/Volume
    indicators, aggregates them deterministically, and generates
    confidence-scored signals with deduplication.
    """

    def __init__(
        self,
        twelve_data_key: Optional[str] = None,
        alpaca_api_key: Optional[str] = None,
        alpaca_secret_key: Optional[str] = None,
        alpaca_base_url: Optional[str] = None,
        history_days: int = 90,
        macd_fast: int = 12,
        macd_slow: int = 26,
        macd_signal: int = 9,
        roc_period: int = 10,
        volume_lookback: int = 20,
        buy_threshold: float = 0.3,
        sell_threshold: float = -0.3,
        min_confidence: float = 0.7,
    ):
        """Initialize the signal engine.

        Args:
            twelve_data_key: Twelve Data API key.
            alpaca_api_key: Alpaca API key.
            alpaca_secret_key: Alpaca secret key.
            alpaca_base_url: Alpaca base URL.
            history_days: Days of historical data to fetch.
            macd_fast: MACD fast EMA period.
            macd_slow: MACD slow EMA period.
            macd_signal: MACD signal EMA period.
            roc_period: ROC lookback period.
            volume_lookback: Volume average lookback period.
            buy_threshold: Score threshold for buy signal.
            sell_threshold: Score threshold for sell signal.
            min_confidence: Minimum confidence to emit a signal.
        """
        self.twelve_data = TwelveDataProvider(api_key=twelve_data_key)
        self.alpaca = AlpacaProvider(
            api_key=alpaca_api_key,
            secret_key=alpaca_secret_key,
            base_url=alpaca_base_url,
        )
        self.history_days = history_days
        self.macd_fast = macd_fast
        self.macd_slow = macd_slow
        self.macd_signal = macd_signal
        self.roc_period = roc_period
        self.volume_lookback = volume_lookback
        self.buy_threshold = buy_threshold
        self.sell_threshold = sell_threshold
        self.min_confidence = min_confidence
        self._signal_history: dict[str, list[str]] = {}  # symbol -> list of directions

    def generate_signals(self, symbols: list[str]) -> list[TechnicalSignal]:
        """Generate buy/sell signals for a list of symbols.

        For each symbol:
        1. Fetch historical OHLCV from Twelve Data
        2. Compute MACD, ROC, Volume indicators
        3. Weighted aggregation
        4. Generate signal if confidence >= min_confidence
        5. Deduplicate against recent signals

        Args:
            symbols: List of stock ticker symbols to analyze.

        Returns:
            List of TechnicalSignal objects that passed confidence threshold.
        """
        signals = []

        for symbol in symbols:
            try:
                signal = self._generate_signal_for_symbol(symbol)
                if signal and self._passes_dedup(symbol, signal.direction):
                    signals.append(signal)
            except Exception as e:
                from stock_market_expert.errors.handler import log_error
                log_error(e, f"Signal generation failed for {symbol}", "step2")

        return signals

    def _generate_signal_for_symbol(self, symbol: str) -> Optional[TechnicalSignal]:
        """Generate a signal for a single symbol.

        Args:
            symbol: Stock ticker symbol.

        Returns:
            TechnicalSignal if confidence >= min_confidence, else None.
        """
        # Fetch historical data
        ohlcv = self.twelve_data.get_historical_ohlcv(
            symbol=symbol,
            interval="1day",
            history_days=self.history_days,
        )

        if not ohlcv:
            return None

        # Compute indicators
        macd_result = compute_macd(
            ohlcv,
            fast=self.macd_fast,
            slow=self.macd_slow,
            signal_period=self.macd_signal,
        )

        roc_result = compute_roc(ohlcv, period=self.roc_period)
        volume_result = compute_volume_score(ohlcv, lookback=self.volume_lookback)

        # Weighted aggregation
        aggregated = weighted_aggregate(
            macd_result=macd_result,
            volume_result=volume_result,
            roc_result=roc_result,
            buy_threshold=self.buy_threshold,
            sell_threshold=self.sell_threshold,
        )

        # Only emit signals that meet confidence threshold
        if aggregated.confidence < self.min_confidence:
            return None
        if aggregated.direction == "hold":
            return None

        # Build reasoning from component scores
        reasoning_parts = [
            f"MACD: {macd_result.direction} (histogram={macd_result.histogram:.4f})",
            f"ROC: {roc_result.value:.2f}% over {roc_result.period}d",
            f"Volume: {volume_result.ratio:.2f}x avg",
            f"Score: {aggregated.score:.4f}",
        ]

        return TechnicalSignal(
            symbol=symbol,
            direction=aggregated.direction,
            confidence=aggregated.confidence,
            score=aggregated.score,
            reasoning="; ".join(reasoning_parts),
        )

    def _passes_dedup(self, symbol: str, direction: str) -> bool:
        """Check if a signal passes deduplication.

        Skips if the same symbol has the same direction signal
        within the current cycle.

        Args:
            symbol: Stock ticker symbol.
            direction: Signal direction ("buy" or "sell").

        Returns:
            True if the signal is unique for this cycle.
        """
        if symbol not in self._signal_history:
            self._signal_history[symbol] = []

        # Check if same direction already exists for this symbol
        if direction in self._signal_history[symbol]:
            return False

        self._signal_history[symbol].append(direction)
        return True

    def reset_dedup(self) -> None:
        """Reset signal deduplication state for a new execution cycle."""
        self._signal_history = {}
