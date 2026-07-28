"""Technical analysis skills for the signal engine.

Provides MACD, ROC, and Volume indicator calculations,
weighted aggregation, and signal generation.
"""

from stock_market_expert.analysis.macd import compute_macd, MacdResult
from stock_market_expert.analysis.roc import compute_roc, RocResult
from stock_market_expert.analysis.volume import compute_volume_score, VolumeResult
from stock_market_expert.analysis.aggregation import weighted_aggregate, AggregatedSignal
from stock_market_expert.analysis.signal_engine import SignalEngine, TechnicalSignal

__all__ = [
    "compute_macd",
    "MacdResult",
    "compute_roc",
    "RocResult",
    "compute_volume_score",
    "VolumeResult",
    "weighted_aggregate",
    "AggregatedSignal",
    "SignalEngine",
    "TechnicalSignal",
]
