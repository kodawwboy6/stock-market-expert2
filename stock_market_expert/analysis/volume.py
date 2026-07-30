"""Volume analysis technical indicator.

Computes volume score relative to average volume for confirmation
of price movements.
"""

import dataclasses
from typing import Any


@dataclasses.dataclass
class VolumeResult:
    """Result of volume analysis.

    Attributes:
        current_volume: Current period's volume.
        average_volume: Average volume over the lookback period.
        ratio: Current volume / average volume ratio.
        direction: "bullish" if ratio > 1 and price up, "bearish" if ratio > 1 and price down, "neutral" otherwise.
        confidence: Confidence in the volume signal (0.0–1.0).
    """

    current_volume: int
    average_volume: float
    ratio: float
    direction: str
    confidence: float


def compute_volume_score(
    ohlcv_data: list[dict[str, Any]],
    lookback: int = 20,
    confidence_high_scale: float = 3.0,
    confidence_low_scale: float = 2.0,
) -> VolumeResult:
    """Compute volume score relative to average.

    Compares current volume to the average over the lookback period.
    A ratio > 1 indicates unusual volume activity.

    Args:
        ohlcv_data: List of OHLCV dicts with 'close' and 'volume' keys.
        lookback: Number of periods for average volume calculation (default 20).
        confidence_high_scale: Ratio threshold for high-confidence scaling.
        confidence_low_scale: Ratio threshold for low-confidence scaling.

    Returns:
        VolumeResult with volume metrics, direction, and confidence.

    Raises:
        ValueError: If insufficient data points.
    """
    if len(ohlcv_data) < lookback + 1:
        raise ValueError(
            f"Insufficient data for volume analysis: need at least {lookback + 1} points, "
            f"got {len(ohlcv_data)}"
        )

    current_volume = int(ohlcv_data[-1]["volume"])

    # Average volume over lookback period (excluding current)
    lookback_data = ohlcv_data[-(lookback + 1):-1]
    average_volume = sum(int(d["volume"]) for d in lookback_data) / len(lookback_data)

    if average_volume == 0:
        return VolumeResult(
            current_volume=current_volume,
            average_volume=0,
            ratio=0,
            direction="neutral",
            confidence=0.0,
        )

    ratio = current_volume / average_volume

    # Determine direction based on volume ratio and price movement
    current_close = float(ohlcv_data[-1]["close"])
    prev_close = float(ohlcv_data[-2]["close"])
    price_up = current_close > prev_close

    if ratio > 1.5:  # Unusual volume
        if price_up:
            direction = "bullish"
        else:
            direction = "bearish"
        confidence = min((ratio - 1.0) / confidence_high_scale, 1.0)
    elif ratio > 1.0:
        direction = "bullish" if price_up else "bearish"
        confidence = min((ratio - 1.0) / confidence_low_scale, 0.5)
    else:
        direction = "neutral"
        confidence = 0.0

    return VolumeResult(
        current_volume=current_volume,
        average_volume=average_volume,
        ratio=ratio,
        direction=direction,
        confidence=confidence,
    )
