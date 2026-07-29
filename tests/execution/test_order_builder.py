"""Tests for OrderBuilder — sells-first ordering and position sizing."""

import pytest

from stock_market_expert.execution.order_builder import ExecutionOrder, OrderBuilder
from stock_market_expert.analysis.signal_engine import TechnicalSignal


@pytest.fixture
def builder():
    """Create an OrderBuilder for testing."""
    return OrderBuilder(max_position_pct=0.10, min_quantity=1)


@pytest.fixture
def mock_signals():
    """Create mock TechnicalSignal objects for testing."""
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
        TechnicalSignal(
            symbol="AAPL",
            direction="sell",
            confidence=0.80,
            score=0.40,
            reasoning="Duplicate signal",
        ),
    ]


def test_build_orders_sells_first(builder, mock_signals):
    """All sell orders should come before buy orders."""
    prices = {"AAPL": 150.0, "GOOGL": 2800.0, "MSFT": 300.0, "TSLA": 250.0}
    orders = builder.build_orders(mock_signals, prices, 100000.0)

    sides = [o.side for o in orders]
    sell_indices = [i for i, s in enumerate(sides) if s == "sell"]
    buy_indices = [i for i, s in enumerate(sides) if s == "buy"]

    if sell_indices and buy_indices:
        assert max(sell_indices) < min(buy_indices), "Sells should come before buys"


def test_build_orders_deduplication(builder, mock_signals):
    """Duplicate signals (same stock, same direction) should be filtered."""
    prices = {"AAPL": 150.0, "GOOGL": 2800.0, "MSFT": 300.0, "TSLA": 250.0}
    orders = builder.build_orders(mock_signals, prices, 100000.0)

    aapl_sells = [o for o in orders if o.symbol == "AAPL" and o.side == "sell"]
    assert len(aapl_sells) <= 1, "Should deduplicate AAPL sell signals"


def test_build_orders_position_sizing_proportional_to_confidence(builder):
    """Higher confidence should result in larger position."""
    high_conf = TechnicalSignal(
        symbol="AAPL", direction="buy", confidence=0.90, score=0.50, reasoning="test"
    )
    low_conf = TechnicalSignal(
        symbol="AAPL", direction="buy", confidence=0.30, score=0.20, reasoning="test"
    )

    prices = {"AAPL": 100.0}
    orders_high = builder.build_orders([high_conf], prices, 100000.0)
    orders_low = builder.build_orders([low_conf], prices, 100000.0)

    assert orders_high[0].quantity >= orders_low[0].quantity


def test_build_orders_market_order_with_day_tif(builder, mock_signals):
    """All orders should be market orders with day time-in-force."""
    prices = {"AAPL": 150.0, "GOOGL": 2800.0, "MSFT": 300.0, "TSLA": 250.0}
    orders = builder.build_orders(mock_signals, prices, 100000.0)

    for order in orders:
        assert order.order_type == "MKT"
        assert order.tif == "DAY"


def test_build_orders_empty_signals(builder):
    """Empty signal list should produce no orders."""
    orders = builder.build_orders([], {}, 100000.0)
    assert orders == []


def test_build_orders_no_price_data(builder):
    """Signals with no price data should be skipped."""
    signals = [
        TechnicalSignal(
            symbol="UNKNOWN",
            direction="buy",
            confidence=0.80,
            score=0.40,
            reasoning="test",
        ),
    ]
    orders = builder.build_orders(signals, {}, 100000.0)
    assert orders == []


def test_deduplication_is_duplicate(builder):
    """is_duplicate should detect same stock, same direction."""
    builder.mark_processed("AAPL", "buy")
    assert builder.is_duplicate("AAPL", "buy") is True
    assert builder.is_duplicate("AAPL", "sell") is False
    assert builder.is_duplicate("GOOGL", "buy") is False


def test_deduplication_clear_on_new_build(builder, mock_signals):
    """Dedup state should clear when building new orders."""
    prices = {"AAPL": 150.0, "GOOGL": 2800.0, "MSFT": 300.0, "TSLA": 250.0}
    builder.build_orders(mock_signals, prices, 100000.0)

    # Same signal should now be allowed on a fresh build
    new_signals = [
        TechnicalSignal(
            symbol="AAPL",
            direction="sell",
            confidence=0.85,
            score=0.45,
            reasoning="test",
        ),
    ]
    orders = builder.build_orders(new_signals, prices, 100000.0)
    assert len(orders) >= 1


def test_apply_order_buy(builder):
    """Applying a buy order should reduce cash and add position."""
    builder.set_portfolio(100000.0, {})
    order = ExecutionOrder(symbol="AAPL", side="buy", quantity=10, confidence=0.8)
    builder.apply_order(order, 150.0)

    assert builder.available_cash == 98500.0
    assert builder.positions.get("AAPL", 0) == 10


def test_apply_order_sell(builder):
    """Applying a sell order should increase cash and reduce position."""
    builder.set_portfolio(100000.0, {"AAPL": 20.0})
    order = ExecutionOrder(symbol="AAPL", side="sell", quantity=5, confidence=0.7)
    builder.apply_order(order, 150.0)

    assert builder.available_cash == 100750.0
    assert builder.positions.get("AAPL", 0) == 15


def test_calculate_quantity_respects_min_quantity(builder):
    """Quantity should never be less than min_quantity."""
    qty = builder.calculate_quantity("AAPL", "buy", 0.10, 100.0)
    assert qty >= builder.min_quantity


def test_execute_sells_before_buses_in_orders(mock_signals):
    """Orders list should have all sells before all buys."""
    builder = OrderBuilder()
    prices = {"AAPL": 150.0, "GOOGL": 2800.0, "MSFT": 300.0, "TSLA": 250.0}
    orders = builder.build_orders(mock_signals, prices, 100000.0)

    seen_buy = False
    for order in orders:
        if order.side == "buy":
            seen_buy = True
        elif seen_buy:
            pytest.fail("Sell order appeared after a buy order")
