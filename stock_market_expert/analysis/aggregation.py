"""Weighted aggregation of technical indicators.

Combines MACD, ROC, and Volume indicator outputs into a single
deterministic score using the formula:
    score = MACD_normalized × 0.5 + Volume_score × 0.3 + ROC_normalized × 0.2
"""

import dataclasses
from typing import Any

from stock_market_expert.analysis.macd import MacdResult
from stock_market_expert.analysis.roc import RocResult
from stock_market_expert.analysis.volume import VolumeResult


@dataclasses.dataclass
class AggregatedSignal:
    """Result of weighted aggregation.

    Attributes:
        score: The combined weighted score.
        macd_component: MACD contribution to the score.
        volume_component: Volume contribution to the score.
        roc_component: ROC contribution to the score.
        direction: "buy" if score > threshold, "sell" if < -threshold, "hold" otherwise.
        confidence: Overall confidence in the aggregated signal.
    """

    score: float
    macd_component: float
    volume_component: float
    roc_component: float
    direction: str
    confidence: float


def weighted_aggregate(
    macd_result: MacdResult,
    volume_result: VolumeResult,
    roc_result: RocResult,
    weights: dict[str, float] = None,
    buy_threshold: float = 0.3,
    sell_threshold: float = -0.3,
) -> AggregatedSignal:
    """Combine technical indicators into a single weighted score.

    Uses deterministic weighted aggregation:
        score = MACD_normalized × 0.5 + Volume_score × 0.3 + ROC_normalized × 0.2

    Args:
        macd_result: MACD indicator result.
        volume_result: Volume indicator result.
        roc_result: ROC indicator result.
        weights: Custom weights dict with keys "macd", "volume", "roc". Defaults to spec weights.
        buy_threshold: Score threshold for buy signal (default 0.3).
        sell_threshold: Score threshold for sell signal (default -0.3).

    Returns:
        AggregatedSignal with combined score and direction.
    """
    if weights is None:
        weights = {"macd": 0.5, "volume": 0.3, "roc": 0.2}

    # Normalize MACD to 0-1 range based on histogram magnitude relative to price
    price = macd_result.macd_line if abs(macd_result.macd_line) > 0 else 1
    macd_normalized = min(abs(macd_result.histogram) / abs(price), 1.0)
    macd_sign = 1.0 if macd_result.histogram > 0 else (-1.0 if macd_result.histogram < 0 else 0.0)
    macd_component = macd_normalized * macd_sign * weights["macd"]

    # Volume contribution: ratio scaled to 0-1, direction from volume_result
    volume_score = min((volume_result.ratio - 1.0) / 2.0, 1.0) if volume_result.ratio > 1.0 else 0.0
    volume_sign = 1.0 if volume_result.direction == "bullish" else (-1.0 if volume_result.direction == "bearish" else 0.0)
    volume_component = volume_score * volume_sign * weights["volume"]

    # ROC contribution: percentage normalized to 0-1
    roc_normalized = min(abs(roc_result.value) / 20, 1.0)
    roc_sign = 1.0 if roc_result.value > 0 else (-1.0 if roc_result.value < 0 else 0.0)
    roc_component = roc_normalized * roc_sign * weights["roc"]

    score = macd_component + volume_component + roc_component

    # Determine direction
    if score > buy_threshold:
        direction = "buy"
    elif score < sell_threshold:
        direction = "sell"
    else:
        direction = "hold"

    # Overall confidence: weighted average of indicator confidences
    macd_conf = macd_result.confidence if macd_result.direction != "neutral" else 0.0
    vol_conf = volume_result.confidence if volume_result.direction != "neutral" else 0.0
    roc_conf = roc_result.confidence if roc_result.direction != "neutral" else 0.0

    total_weight = weights["macd"] + weights["volume"] + weights["roc"]
    confidence = (macd_conf * weights["macd"] + vol_conf * weights["volume"] + roc_conf * weights["roc"]) / total_weight if total_weight > 0 else 0.0

    return AggregatedSignal(
        score=score,
        macd_component=macd_component,
        volume_component=volume_component,
        roc_component=roc_component,
        direction=direction,
        confidence=confidence,
    )
