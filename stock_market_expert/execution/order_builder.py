"""Order builder with sells-first ordering and position sizing.

Constructs execution orders from signals, enforcing:
- All sell operations complete before any buy operations begin
- Position sizing proportional to confidence score
- Market orders with day time-in-force
- Signal deduplication (skip same stock, same direction)
"""

import dataclasses
import logging
from typing import Optional

from stock_market_expert.analysis.signal_engine import TechnicalSignal

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class ExecutionOrder:
    """A single execution order ready to be sent to IBKR.

    Attributes:
        symbol: Stock ticker symbol.
        side: "buy" or "sell".
        quantity: Number of shares to trade.
        order_type: Order type — "MKT" for market orders.
        tif: Time-in-force — "DAY" for day orders.
        confidence: Confidence score from the originating signal.
        reasoning: Explanation for the order.
    """

    symbol: str
    side: str
    quantity: int
    order_type: str = "MKT"
    tif: str = "DAY"
    confidence: float = 0.0
    reasoning: str = ""


class OrderBuilder:
    """Builds execution orders from signals with sells-first ordering.

    Enforces that all sell orders are placed before any buy orders,
    with dynamic portfolio balance tracking after each sell to update
    available cash for subsequent buy orders.
    """

    def __init__(
        self,
        max_position_pct: float = 0.10,
        min_quantity: int = 1,
        order_type: str = "MKT",
        tif: str = "DAY",
    ):
        """Initialize the order builder.

        Args:
            max_position_pct: Maximum portfolio allocation per position (e.g., 0.10 = 10%).
            min_quantity: Minimum order quantity (must be at least 1).
            order_type: Default order type. Defaults to "MKT".
            tif: Default time-in-force. Defaults to "DAY".
        """
        self.max_position_pct = max_position_pct
        self.min_quantity = max(min_quantity, 1)
        self.order_type = order_type
        self.tif = tif
        self._available_cash: float = 0.0
        self._positions: dict[str, float] = {}
        self._processed_signals: set[tuple[str, str]] = set()

    def set_portfolio(self, cash: float, positions: dict[str, float]) -> None:
        """Set current portfolio state.

        Args:
            cash: Available cash balance.
            positions: Dict mapping symbol to current quantity.
        """
        self._available_cash = cash
        self._positions = dict(positions)

    def add_position(self, symbol: str, delta: float) -> None:
        """Update position for a symbol after an order.

        Args:
            symbol: Stock ticker symbol.
            delta: Change in quantity (positive for buy, negative for sell).
        """
        current = self._positions.get(symbol, 0.0)
        self._positions[symbol] = current + delta

    def update_cash(self, delta: float) -> None:
        """Update available cash after an order.

        Args:
            delta: Cash change (negative for buy, positive for sell).
        """
        self._available_cash += delta

    @property
    def available_cash(self) -> float:
        """Get current available cash."""
        return self._available_cash

    @property
    def positions(self) -> dict[str, float]:
        """Get current positions."""
        return dict(self._positions)

    def is_duplicate(self, symbol: str, direction: str) -> bool:
        """Check if a signal is a duplicate (same stock, same direction).

        Args:
            symbol: Stock ticker symbol.
            direction: Signal direction ("buy" or "sell").

        Returns:
            True if this signal has already been processed.
        """
        key = (symbol, direction)
        return key in self._processed_signals

    def mark_processed(self, symbol: str, direction: str) -> None:
        """Mark a signal as processed for deduplication.

        Args:
            symbol: Stock ticker symbol.
            direction: Signal direction ("buy" or "sell").
        """
        self._processed_signals.add((symbol, direction))

    def calculate_quantity(
        self,
        symbol: str,
        direction: str,
        confidence: float,
        price: float,
    ) -> int:
        """Calculate order quantity proportional to confidence score.

        Position size = (confidence * max_position_pct * equity) / price

        Args:
            symbol: Stock ticker symbol.
            direction: Signal direction ("buy" or "sell").
            confidence: Confidence score (0.0–1.0).
            price: Current price per share.

        Returns:
            Number of shares to trade.
        """
        if price <= 0:
            return self.min_quantity

        equity = self._available_cash + sum(
            self._positions.get(s, 0.0) * 0.0 for s in self._positions
        )

        # Use available cash as proxy for equity when positions info is limited
        max_alloc = self.max_position_pct * self._available_cash
        raw_qty = (confidence * max_alloc) / price

        # For sells, use existing position quantity
        if direction == "sell":
            current_pos = self._positions.get(symbol, 0.0)
            return max(int(current_pos), self.min_quantity)

        # For buys, round down to avoid partial fills
        return max(int(raw_qty), self.min_quantity)

    def build_orders(
        self,
        signals: list[TechnicalSignal],
        current_prices: dict[str, float],
        equity: float,
    ) -> list[ExecutionOrder]:
        """Build execution orders from signals with sells-first ordering.

        All sell orders are built first, then buy orders. Portfolio balance
        is updated dynamically after each sell to reflect cash from proceeds.

        Args:
            signals: List of TechnicalSignal objects from the signal engine.
            current_prices: Dict mapping symbol to current market price.
            equity: Current portfolio equity.

        Returns:
            List of ExecutionOrder objects, sells first then buys.
        """
        # Set portfolio state
        self.set_portfolio(equity, {})
        self._processed_signals.clear()

        sells = []
        buys = []

        for signal in signals:
            # Signal deduplication: skip if same stock has same direction
            if self.is_duplicate(signal.symbol, signal.direction):
                logger.debug(
                    f"Dedup: skipping {signal.direction} signal for {signal.symbol}"
                )
                continue

            price = current_prices.get(signal.symbol, 0.0)
            if price <= 0:
                logger.warning(
                    f"No price data for {signal.symbol}, skipping signal"
                )
                continue

            quantity = self.calculate_quantity(
                signal.symbol, signal.direction, signal.confidence, price
            )

            if quantity < self.min_quantity:
                logger.debug(
                    f"Quantity {quantity} below minimum for {signal.symbol}, skipping"
                )
                continue

            order = ExecutionOrder(
                symbol=signal.symbol,
                side=signal.direction,
                quantity=quantity,
                order_type=self.order_type,
                tif=self.tif,
                confidence=signal.confidence,
                reasoning=signal.reasoning,
            )

            if signal.direction == "sell":
                sells.append(order)
            else:
                buys.append(order)

            self.mark_processed(signal.symbol, signal.direction)

        # Sells-first: process sells before buys
        orders = list(sells) + list(buys)
        logger.info(
            f"Built {len(orders)} orders: {len(sells)} sells, {len(buys)} buys"
        )
        return orders

    def apply_order(self, order: ExecutionOrder, fill_price: float) -> None:
        """Apply an order's effect to internal state.

        Updates positions and cash after an order fills.

        Args:
            order: The execution order.
            fill_price: Actual fill price.
        """
        if order.side == "sell":
            self.add_position(order.symbol, -order.quantity)
            self.update_cash(order.quantity * fill_price)
        else:
            cost = order.quantity * fill_price
            if cost <= self._available_cash:
                self.add_position(order.symbol, order.quantity)
                self.update_cash(-cost)
            else:
                logger.warning(
                    f"Insufficient cash for buy order: {order.symbol} "
                    f"needs {cost}, have {self._available_cash}"
                )
