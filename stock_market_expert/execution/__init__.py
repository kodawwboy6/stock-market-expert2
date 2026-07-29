"""Execution layer for Interactive Brokers paper trading.

Provides IBKR connection management, order building with sells-first
ordering, dynamic portfolio tracking, position sizing, and signal
deduplication.
"""

from stock_market_expert.execution.ibkr_client import IBKRClient
from stock_market_expert.execution.order_builder import OrderBuilder, ExecutionOrder
from stock_market_expert.execution.portfolio_tracker import PortfolioTracker
from stock_market_expert.execution.executor import ExecutionEngine

__all__ = [
    "IBKRClient",
    "OrderBuilder",
    "ExecutionOrder",
    "PortfolioTracker",
    "ExecutionEngine",
]
