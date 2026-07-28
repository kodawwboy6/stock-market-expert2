"""MACD (Moving Average Convergence Divergence) technical indicator.

Computes MACD (12, 26, 9) from OHLCV data and returns a directional
value and confidence score for signal generation.
"""

import dataclasses
from typing import Any


@dataclasses.dataclass
class MacdResult:
    """Result of MACD computation.

    Attributes:
        macd_line: The MACD line value (EMA12 - EMA26).
        signal_line: The signal line value (EMA9 of MACD line).
        histogram: The histogram value (MACD line - signal line).
        direction: "bullish" if histogram > 0, "bearish" if < 0, "neutral" if 0.
        confidence: Confidence in the direction (0.0–1.0), based on histogram magnitude.
    """

    macd_line: float
    signal_line: float
    histogram: float
    direction: str
    confidence: float


def _compute_ema(values: list[float], period: int) -> list[float]:
    """Compute Exponential Moving Average for a list of values.

    Args:
        values: List of price values (typically close prices).
        period: EMA period.

    Returns:
        List of EMA values aligned with input.
    """
    if not values:
        return []

    ema = [values[0]]
    multiplier = 2.0 / (period + 1)

    for i in range(1, len(values)):
        new_ema = (values[i] - ema[-1]) * multiplier + ema[-1]
        ema.append(new_ema)

    return ema


def compute_macd(ohlcv_data: list[dict[str, Any]], fast: int = 12, slow: int = 26, signal_period: int = 9) -> MacdResult:
    """Compute MACD from OHLCV data.

    Args:
        ohlcv_data: List of OHLCV dicts with at least a 'close' key.
        fast: Fast EMA period (default 12).
        slow: Slow EMA period (default 26).
        signal_period: Signal line EMA period (default 9).

    Returns:
        MacdResult with macd_line, signal_line, histogram, direction, and confidence.

    Raises:
        ValueError: If insufficient data points.
    """
    if len(ohlcv_data) < slow + signal_period:
        raise ValueError(
            f"Insufficient data for MACD: need at least {slow + signal_period} points, "
            f"got {len(ohlcv_data)}"
        )

    closes = [float(point["close"]) for point in ohlcv_data]

    ema_fast = _compute_ema(closes, fast)
    ema_slow = _compute_ema(closes, slow)

    # MACD line = EMA(fast) - EMA(slow)
    macd_line = [f - s for f, s in zip(ema_fast, ema_slow)]

    # Signal line = EMA(signal_period) of MACD line
    signal_line_values = _compute_ema(macd_line, signal_period)

    # Use the latest values
    latest_macd = macd_line[-1]
    latest_signal = signal_line_values[-1]
    histogram = latest_macd - latest_signal

    # Determine direction and confidence
    if histogram > 0:
        direction = "bullish"
        # Confidence scales with histogram magnitude relative to price
        price = closes[-1]
        normalized_histogram = abs(histogram) / price if price > 0 else 0
        confidence = min(normalized_histogram * 10, 1.0)
    elif histogram < 0:
        direction = "bearish"
        price = closes[-1]
        normalized_histogram = abs(histogram) / price if price > 0 else 0
        confidence = min(normalized_histogram * 10, 1.0)
    else:
        direction = "neutral"
        confidence = 0.0

    return MacdResult(
        macd_line=latest_macd,
        signal_line=latest_signal,
        histogram=histogram,
        direction=direction,
        confidence=confidence,
    )
