"""Dynamic portfolio tracker for execution layer.

Tracks portfolio balance, positions, and P&L through the execution
lifecycle. Supports real-time updates after each order fill.
"""

import dataclasses
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class PortfolioSnapshot:
    """A point-in-time snapshot of portfolio state.

    Attributes:
        cash: Available cash balance.
        equity: Total portfolio equity (cash + positions).
        positions: Dict mapping symbol to current quantity.
        unrealized_pnl: Total unrealized P&L across all positions.
        realized_pnl: Total realized P&L from closed positions.
        timestamp: When the snapshot was taken.
    """

    cash: float
    equity: float
    positions: dict[str, float]
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for serialization."""
        return {
            "cash": self.cash,
            "equity": self.equity,
            "positions": dict(self.positions),
            "unrealized_pnl": self.unrealized_pnl,
            "realized_pnl": self.realized_pnl,
        }


class PortfolioTracker:
    """Dynamic portfolio balance tracker.

    Updates cash and positions after each order fill, tracking
    unrealized and realized P&L.
    """

    def __init__(self):
        """Initialize the portfolio tracker."""
        self._cash: float = 0.0
        self._positions: dict[str, float] = {}
        self._avg_costs: dict[str, float] = {}  # symbol -> average cost per share
        self._realized_pnl: float = 0.0
        self._snapshot_count: int = 0

    @property
    def cash(self) -> float:
        """Get current cash balance."""
        return self._cash

    @property
    def positions(self) -> dict[str, float]:
        """Get current positions."""
        return dict(self._positions)

    @property
    def realized_pnl(self) -> float:
        """Get total realized P&L."""
        return self._realized_pnl

    def set_cash(self, cash: float) -> None:
        """Set the initial cash balance.

        Args:
            cash: Initial cash amount.
        """
        self._cash = cash

    def update_after_sell(self, symbol: str, quantity: float, sell_price: float) -> float:
        """Update portfolio after a sell order fills.

        Dynamically updates cash and reduces position. Calculates
        realized P&L from the sell.

        Args:
            symbol: Stock ticker symbol.
            quantity: Number of shares sold.
            sell_price: Fill price per share.

        Returns:
            Realized P&L from this sell.
        """
        current_qty = self._positions.get(symbol, 0.0)
        if current_qty <= 0:
            logger.warning(f"No position to sell for {symbol}")
            return 0.0

        # Calculate realized P&L
        avg_cost = self._avg_costs.get(symbol, 0.0)
        if avg_cost > 0:
            partial_pnl = (sell_price - avg_cost) * min(quantity, current_qty)
            self._realized_pnl += partial_pnl

        # Update position
        new_qty = current_qty - quantity
        if new_qty <= 0:
            del self._positions[symbol]
            self._avg_costs.pop(symbol, None)
        else:
            self._positions[symbol] = new_qty

        # Update cash
        self._cash += quantity * sell_price
        logger.info(
            f"Sell update: {symbol} {quantity}@{sell_price:.2f}, "
            f"P&L={partial_pnl:.2f}, cash={self._cash:.2f}"
        )
        return partial_pnl

    def update_after_buy(self, symbol: str, quantity: int, buy_price: float) -> None:
        """Update portfolio after a buy order fills.

        Updates cash and adds/increases position with average cost tracking.

        Args:
            symbol: Stock ticker symbol.
            quantity: Number of shares bought.
            buy_price: Fill price per share.
        """
        if buy_price <= 0 or quantity <= 0:
            logger.warning(f"Invalid buy update: {symbol} {quantity}@{buy_price}")
            return

        cost = quantity * buy_price
        if cost > self._cash:
            logger.warning(
                f"Insufficient cash for buy: {symbol} needs {cost}, have {self._cash}"
            )
            return

        # Update average cost
        current_qty = self._positions.get(symbol, 0.0)
        if current_qty > 0:
            old_cost = self._avg_costs.get(symbol, 0.0)
            total_shares = current_qty + quantity
            self._avg_costs[symbol] = (
                (current_qty * old_cost + quantity * buy_price) / total_shares
            )
        else:
            self._avg_costs[symbol] = buy_price

        self._positions[symbol] = current_qty + quantity
        self._cash -= cost
        logger.info(
            f"Buy update: {symbol} {quantity}@{buy_price:.2f}, cash={self._cash:.2f}"
        )

    def get_unrealized_pnl(self, current_prices: dict[str, float]) -> float:
        """Calculate total unrealized P&L from current positions.

        Args:
            current_prices: Dict mapping symbol to current market price.

        Returns:
            Total unrealized P&L.
        """
        unrealized = 0.0
        for symbol, qty in self._positions.items():
            if qty > 0 and symbol in current_prices:
                price = current_prices[symbol]
                avg_cost = self._avg_costs.get(symbol, 0.0)
                if avg_cost > 0:
                    unrealized += (price - avg_cost) * qty
        return unrealized

    def get_equity(self, current_prices: dict[str, float]) -> float:
        """Calculate total portfolio equity.

        Args:
            current_prices: Dict mapping symbol to current market price.

        Returns:
            Total equity (cash + unrealized positions).
        """
        equity = self._cash
        for symbol, qty in self._positions.items():
            if qty > 0 and symbol in current_prices:
                equity += qty * current_prices[symbol]
        return equity

    def take_snapshot(self) -> PortfolioSnapshot:
        """Take a point-in-time snapshot of portfolio state.

        Returns:
            PortfolioSnapshot with current state.
        """
        self._snapshot_count += 1
        return PortfolioSnapshot(
            cash=self._cash,
            equity=self.get_equity({}),
            positions=dict(self._positions),
            unrealized_pnl=0.0,
            realized_pnl=self._realized_pnl,
        )

    def get_state(self, current_prices: Optional[dict[str, float]] = None) -> dict[str, Any]:
        """Get current portfolio state.

        Args:
            current_prices: Optional current prices for equity calculation.

        Returns:
            Dict with cash, equity, positions, unrealized_pnl, realized_pnl.
        """
        prices = current_prices or {}
        unrealized = self.get_unrealized_pnl(prices)
        equity = self.get_equity(prices)

        return {
            "cash": self._cash,
            "equity": equity,
            "positions": dict(self._positions),
            "unrealized_pnl": unrealized,
            "realized_pnl": self._realized_pnl,
        }
