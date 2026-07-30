"""ROC (Rate of Change) technical indicator.

Computes ROC over a configurable period from OHLCV data and returns
a directional value and confidence score for signal generation.
"""

import dataclasses
from typing import Any


@dataclasses.dataclass
class RocResult:
    """Result of ROC computation.

    Attributes:
        value: The ROC percentage value.
        period: The period used for calculation.
        direction: "bullish" if value > 0, "bearish" if < 0, "neutral" if 0.
        confidence: Confidence in the direction (0.0–1.0).
    """

    value: float
    period: int
    direction: str
    confidence: float


def compute_roc(
    ohlcv_data: list[dict[str, Any]],
    period: int = 10,
    confidence_scale: float = 20.0,
) -> RocResult:
    """Compute Rate of Change from OHLCV data.

    ROC = ((Close - Close_n_days_ago) / Close_n_days_ago) * 100

    Args:
        ohlcv_data: List of OHLCV dicts with at least a 'close' key.
        period: Number of periods to look back (default 10).
        confidence_scale: ROC percentage at which confidence reaches 1.0.

    Returns:
        RocResult with value, period, direction, and confidence.

    Raises:
        ValueError: If insufficient data points.
    """
    if len(ohlcv_data) < period + 1:
        raise ValueError(
            f"Insufficient data for ROC: need at least {period + 1} points, "
            f"got {len(ohlcv_data)}"
        )

    current_close = float(ohlcv_data[-1]["close"])
    past_close = float(ohlcv_data[-(period + 1)]["close"])

    if past_close == 0:
        return RocResult(value=0.0, period=period, direction="neutral", confidence=0.0)

    roc_value = ((current_close - past_close) / past_close) * 100

    # Determine direction and confidence
    if roc_value > 0:
        direction = "bullish"
        confidence = min(abs(roc_value) / confidence_scale, 1.0)
    elif roc_value < 0:
        direction = "bearish"
        confidence = min(abs(roc_value) / confidence_scale, 1.0)
    else:
        direction = "neutral"
        confidence = 0.0

    return RocResult(
        value=roc_value,
        period=period,
        direction=direction,
        confidence=confidence,
    )
