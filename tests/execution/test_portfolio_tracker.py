"""Tests for PortfolioTracker — dynamic balance tracking."""

import pytest

from stock_market_expert.execution.portfolio_tracker import PortfolioTracker


@pytest.fixture
def tracker():
    """Create a PortfolioTracker for testing."""
    return PortfolioTracker()


def test_initial_state(tracker):
    """Initial state should have zero cash and no positions."""
    assert tracker.cash == 0.0
    assert tracker.positions == {}
    assert tracker.realized_pnl == 0.0


def test_set_cash(tracker):
    """set_cash should update the cash balance."""
    tracker.set_cash(100000.0)
    assert tracker.cash == 100000.0


def test_update_after_sell(tracker):
    """Selling shares should reduce position and increase cash."""
    tracker.set_cash(100000.0)
    tracker._positions["AAPL"] = 100.0
    tracker._avg_costs["AAPL"] = 150.0

    pnl = tracker.update_after_sell("AAPL", 30, 155.0)

    assert tracker.cash == 100000.0 + 30 * 155.0
    assert tracker.positions.get("AAPL", 0) == 70.0
    assert pnl == pytest.approx(30 * (155.0 - 150.0))


def test_update_after_sell_all_positions(tracker):
    """Selling all shares should remove the position."""
    tracker.set_cash(100000.0)
    tracker._positions["AAPL"] = 50.0
    tracker._avg_costs["AAPL"] = 150.0

    tracker.update_after_sell("AAPL", 50, 160.0)

    assert "AAPL" not in tracker.positions
    assert "AAPL" not in tracker._avg_costs


def test_update_after_buy(tracker):
    """Buying shares should increase position and reduce cash."""
    tracker.set_cash(100000.0)
    tracker.update_after_buy("AAPL", 10, 150.0)

    assert tracker.cash == 98500.0
    assert tracker.positions.get("AAPL", 0) == 10


def test_update_after_buy_increases_position(tracker):
    """Buying more of an existing position should increase quantity."""
    tracker.set_cash(100000.0)
    tracker._positions["AAPL"] = 10.0
    tracker._avg_costs["AAPL"] = 150.0

    tracker.update_after_buy("AAPL", 10, 160.0)

    assert tracker.positions.get("AAPL", 0) == 20.0
    assert tracker._avg_costs["AAPL"] == pytest.approx(155.0)


def test_update_after_buy_insufficient_cash(tracker):
    """Buying more than cash should not reduce cash."""
    tracker.set_cash(100.0)
    initial_cash = tracker.cash
    tracker.update_after_buy("AAPL", 1000, 150.0)

    assert tracker.cash == initial_cash
    assert "AAPL" not in tracker.positions


def test_get_unrealized_pnl(tracker):
    """Unrealized P&L should reflect current prices vs avg cost."""
    tracker.set_cash(100000.0)
    tracker._positions["AAPL"] = 100.0
    tracker._avg_costs["AAPL"] = 150.0

    pnl = tracker.get_unrealized_pnl({"AAPL": 160.0})
    assert pnl == pytest.approx(100 * (160.0 - 150.0))


def test_get_equity(tracker):
    """Equity should be cash + position values."""
    tracker.set_cash(85000.0)
    tracker._positions["AAPL"] = 100.0

    equity = tracker.get_equity({"AAPL": 150.0})
    assert equity == pytest.approx(85000.0 + 100 * 150.0)


def test_take_snapshot(tracker):
    """take_snapshot should return a PortfolioSnapshot."""
    tracker.set_cash(100000.0)
    snapshot = tracker.take_snapshot()

    assert snapshot.cash == 100000.0
    assert snapshot.positions == {}
    assert snapshot.to_dict()["cash"] == 100000.0


def test_get_state(tracker):
    """get_state should return a dict with all portfolio info."""
    tracker.set_cash(100000.0)
    tracker._positions["AAPL"] = 50.0
    tracker._avg_costs["AAPL"] = 150.0

    state = tracker.get_state({"AAPL": 155.0})

    assert state["cash"] == 100000.0
    assert state["positions"]["AAPL"] == 50.0
    assert state["realized_pnl"] == 0.0
    assert "equity" in state
    assert "unrealized_pnl" in state
