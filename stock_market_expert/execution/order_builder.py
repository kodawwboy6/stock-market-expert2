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
from stock_market_expert.config.loader import load_config

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
        applied: Whether this order has already been applied to a tracker.
    """

    symbol: str
    side: str
    quantity: int
    order_type: str = "MKT"
    tif: str = "DAY"
    confidence: float = 0.0
    reasoning: str = ""
    applied: bool = False

    def apply(self, portfolio_tracker: "PortfolioTracker", fill_price: float) -> bool:
        """Apply this order to the portfolio tracker.

        Idempotent: returns False if already applied.

        Args:
            portfolio_tracker: The tracker to update.
            fill_price: Actual fill price per share.

        Returns:
            True if the order was applied, False if already applied.
        """
        if self.applied:
            return False

        if self.side == "sell":
            portfolio_tracker.update_after_sell(self.symbol, self.quantity, fill_price)
        else:
            portfolio_tracker.update_after_buy(self.symbol, self.quantity, fill_price)

        self.applied = True
        return True


class OrderBuilder:
    """Builds execution orders from signals with sells-first ordering.

    Reads portfolio state from the injected PortfolioTracker (sole source of truth).
    Enforces that all sell orders are placed before any buy orders.
    """

    def __init__(
        self,
        portfolio_tracker: "PortfolioTracker",
        max_position_pct: Optional[float] = None,
        min_quantity: Optional[int] = None,
        order_type: Optional[str] = None,
        tif: Optional[str] = None,
    ):
        """Initialize the order builder.

        Args:
            portfolio_tracker: The sole source of truth for portfolio state.
            max_position_pct: Maximum portfolio allocation per position (e.g., 0.10 = 10%). Defaults to MAX_POSITION_PCT env var.
            min_quantity: Minimum order quantity (must be at least 1). Defaults to MIN_ORDER_QUANTITY env var.
            order_type: Default order type. Defaults to ORDER_TYPE env var.
            tif: Default time-in-force. Defaults to "DAY".
        """
        cfg = load_config()
        self.portfolio_tracker = portfolio_tracker
        self.max_position_pct = max_position_pct if max_position_pct is not None else cfg.max_position_pct
        self.min_quantity = max(min_quantity if min_quantity is not None else cfg.min_order_quantity, 1)
        self.order_type = order_type if order_type is not None else cfg.order_type
        self.tif = tif if tif is not None else "DAY"
        self._processed_signals: set[tuple[str, str]] = set()

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
        current_prices: dict[str, float] | None = None,
    ) -> int:
        """Calculate order quantity proportional to confidence score.

        Position size = (confidence * max_position_pct * equity) / price

        Reads equity and positions from the injected PortfolioTracker.

        Args:
            symbol: Stock ticker symbol.
            direction: Signal direction ("buy" or "sell").
            confidence: Confidence score (0.0–1.0).
            price: Current price per share.
            current_prices: Optional prices for valuing positions.

        Returns:
            Number of shares to trade.
        """
        if price <= 0:
            return self.min_quantity

        equity = self.portfolio_tracker.get_equity(current_prices)
        max_alloc = self.max_position_pct * equity
        raw_qty = (confidence * max_alloc) / price

        # For sells, use existing position quantity
        if direction == "sell":
            current_pos = self.portfolio_tracker.positions.get(symbol, 0.0)
            return max(int(current_pos), self.min_quantity)

        # For buys, round down to avoid partial fills
        return max(int(raw_qty), self.min_quantity)

    def build_orders(
        self,
        signals: list[TechnicalSignal],
        current_prices: dict[str, float],
    ) -> list[ExecutionOrder]:
        """Build execution orders from signals with sells-first ordering.

        All sell orders are built first, then buy orders. Reads portfolio
        state from the injected PortfolioTracker.

        Args:
            signals: List of TechnicalSignal objects from the signal engine.
            current_prices: Dict mapping symbol to current market price.

        Returns:
            List of ExecutionOrder objects, sells first then buys.
        """
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
                signal.symbol, signal.direction, signal.confidence, price,
                current_prices,
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
