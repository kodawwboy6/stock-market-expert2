"""Tests for ExecutionEngine — orchestrator."""

import pytest

from stock_market_expert.execution.executor import ExecutionEngine, ExecutionResult
from stock_market_expert.execution.ibkr_client import IBKRClient
from stock_market_expert.execution.order_builder import OrderBuilder
from stock_market_expert.execution.portfolio_tracker import PortfolioTracker
from stock_market_expert.analysis.signal_engine import TechnicalSignal


@pytest.fixture
def signals():
    """Create mock signals for testing."""
    return [
        TechnicalSignal(
            symbol="AAPL",
            direction="sell",
            confidence=0.85,
            score=0.45,
            reasoning="MACD bearish crossover",
        ),
        TechnicalSignal(
            symbol="GOOGL",
            direction="sell",
            confidence=0.70,
            score=-0.35,
            reasoning="ROC negative momentum",
        ),
        TechnicalSignal(
            symbol="MSFT",
            direction="buy",
            confidence=0.90,
            score=0.52,
            reasoning="MACD bullish crossover",
        ),
        TechnicalSignal(
            symbol="TSLA",
            direction="buy",
            confidence=0.60,
            score=0.31,
            reasoning="Volume confirmation",
        ),
    ]


@pytest.fixture
def engine():
    """Create an ExecutionEngine in paper mode."""
    return ExecutionEngine(paper_account=True)


def test_init_defaults(engine):
    """ExecutionEngine should use default paper mode."""
    assert engine.paper_account is True
    assert isinstance(engine.ibkr, IBKRClient)
    assert isinstance(engine.order_builder, OrderBuilder)
    assert isinstance(engine.portfolio_tracker, PortfolioTracker)


def test_init_custom_components():
    """ExecutionEngine should accept custom components."""
    ibkr = IBKRClient(paper_account=True)
    tracker = PortfolioTracker()
    builder = OrderBuilder(tracker)
    engine = ExecutionEngine(
        ibkr_client=ibkr,
        order_builder=builder,
        portfolio_tracker=tracker,
        paper_account=True,
    )
    assert engine.ibkr is ibkr
    assert engine.order_builder is builder
    assert engine.portfolio_tracker is tracker


@pytest.mark.asyncio
async def test_run_with_initial_cash(engine, signals):
    """run should execute orders with initial cash."""
    prices = {"AAPL": 150.0, "GOOGL": 2800.0, "MSFT": 300.0, "TSLA": 250.0}
    result = await engine.run(signals, prices, initial_cash=100000.0)

    assert isinstance(result, ExecutionResult)
    assert len(result.orders) > 0
    assert isinstance(result.portfolio_state, dict)


@pytest.mark.asyncio
async def test_run_sells_first(engine, signals):
    """Orders should be sells first, then buys."""
    prices = {"AAPL": 150.0, "GOOGL": 2800.0, "MSFT": 300.0, "TSLA": 250.0}
    result = await engine.run(signals, prices, initial_cash=100000.0)

    sides = [o.side for o in result.orders]
    sell_indices = [i for i, s in enumerate(sides) if s == "sell"]
    buy_indices = [i for i, s in enumerate(sides) if s == "buy"]

    if sell_indices and buy_indices:
        assert max(sell_indices) < min(buy_indices)


@pytest.mark.asyncio
async def test_run_empty_signals(engine):
    """run should handle empty signals gracefully."""
    result = await engine.run([], {}, initial_cash=100000.0)
    assert isinstance(result, ExecutionResult)
    assert len(result.orders) == 0


@pytest.mark.asyncio
async def test_execution_result_to_dict(engine, signals):
    """ExecutionResult.to_dict should serialize correctly."""
    prices = {"AAPL": 150.0, "GOOGL": 2800.0, "MSFT": 300.0, "TSLA": 250.0}
    result = await engine.run(signals, prices, initial_cash=100000.0)

    d = result.to_dict()
    assert "orders" in d
    assert "fills" in d
    assert "portfolio_state" in d
    assert "errors" in d
    assert "timestamp" in d


@pytest.mark.asyncio
async def test_execute_sells_first_method(engine, signals):
    """execute_sells_first should process sells before buys."""
    prices = {"AAPL": 150.0, "GOOGL": 2800.0, "MSFT": 300.0, "TSLA": 250.0}
    result = await engine.execute_sells_first(signals, prices, 100000.0)

    assert isinstance(result, ExecutionResult)
    assert len(result.orders) > 0

    # Check sells-first ordering
    sides = [o.side for o in result.orders]
    seen_buy = False
    for side in sides:
        if side == "buy":
            seen_buy = True
        elif seen_buy:
            pytest.fail("Sell appeared after buy")


@pytest.mark.asyncio
async def test_portfolio_state_updated(engine, signals):
    """Portfolio state should reflect executed orders."""
    prices = {"AAPL": 150.0, "GOOGL": 2800.0, "MSFT": 300.0, "TSLA": 250.0}
    result = await engine.run(signals, prices, initial_cash=100000.0)

    assert "cash" in result.portfolio_state
    assert "equity" in result.portfolio_state
    assert "positions" in result.portfolio_state
