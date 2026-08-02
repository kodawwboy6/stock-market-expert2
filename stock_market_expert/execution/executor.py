"""Execution engine orchestrator.

Orchestrates the full execution flow:
1. Connect to IBKR
2. Fetch signals from the signal engine
3. Deduplicate signals
4. Execute sells-first ordering
5. Dynamic portfolio balance tracking
6. Position sizing proportional to confidence
7. Place market orders with day time-in-force
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from stock_market_expert.config.loader import load_config
from stock_market_expert.execution.ibkr_client import IBKRClient
from stock_market_expert.execution.order_builder import ExecutionOrder, OrderBuilder
from stock_market_expert.execution.portfolio_tracker import PortfolioTracker

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """Result of the execution engine run.

    Attributes:
        orders: List of execution orders that were processed.
        fills: Dict mapping order key to fill info.
        portfolio_state: Final portfolio state after execution.
        errors: List of error messages from failed orders.
        timestamp: When execution completed.
    """

    orders: list[ExecutionOrder] = field(default_factory=list)
    fills: dict[str, dict[str, Any]] = field(default_factory=dict)
    portfolio_state: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for serialization."""
        return {
            "orders": [
                {
                    "symbol": o.symbol,
                    "side": o.side,
                    "quantity": o.quantity,
                    "order_type": o.order_type,
                    "tif": o.tif,
                    "confidence": o.confidence,
                }
                for o in self.orders
            ],
            "fills": self.fills,
            "portfolio_state": self.portfolio_state,
            "errors": self.errors,
            "timestamp": self.timestamp,
        }


class ExecutionEngine:
    """Orchestrates execution of trading signals.

    Manages the full lifecycle: connection, signal processing,
    sells-first ordering, position sizing, and order placement.
    """

    def __init__(
        self,
        ibkr_client: Optional[IBKRClient] = None,
        order_builder: Optional[OrderBuilder] = None,
        portfolio_tracker: Optional[PortfolioTracker] = None,
        paper_account: bool = True,
        order_type: Optional[str] = None,
        initial_cash: Optional[float] = None,
        cycle_deadline: Optional[float] = None,
    ):
        """Initialize the execution engine.

        Args:
            ibkr_client: IBKR client instance.
            order_builder: Order builder instance.
            portfolio_tracker: Portfolio tracker instance.
            paper_account: Whether to use paper trading mode.
            order_type: Default order type for all orders (e.g. "MKT", "LMT"). Defaults to ORDER_TYPE env var.
            initial_cash: Initial cash balance for paper mode. Defaults to INITIAL_CASH env var.
            cycle_deadline: Epoch time — shared across all IBKR retries
                for this execution cycle. Set at the start of each run
                so retries leave enough time for the next cycle.
        """
        cfg = load_config()
        self.portfolio_tracker = portfolio_tracker or PortfolioTracker()
        self.order_builder = order_builder or OrderBuilder(
            self.portfolio_tracker, order_type=order_type or cfg.order_type,
        )
        self.ibkr = ibkr_client or IBKRClient(paper_account=paper_account)
        self.paper_account = paper_account
        self.order_type = order_type or cfg.order_type
        self._initial_cash = initial_cash if initial_cash is not None else cfg.initial_cash
        self._cycle_deadline = cycle_deadline

    async def run(
        self,
        signals: list[Any],
        current_prices: Optional[dict[str, float]] = None,
        initial_cash: Optional[float] = None,
    ) -> ExecutionResult:
        """Run the full execution pipeline.

        1. Connect to IBKR
        2. Fetch portfolio state
        3. Build orders with sells-first ordering
        4. Execute orders (sells first, then buys)
        5. Update portfolio after each order
        6. Return execution result

        Args:
            signals: List of TechnicalSignal objects from the signal engine.
            current_prices: Dict mapping symbol to current market price.
            initial_cash: Initial cash balance (for paper mode without live account).

        Returns:
            ExecutionResult with orders, fills, and portfolio state.
        """
        # Set the shared deadline for all IBKR retries in this cycle
        cfg = load_config()
        cycle_deadline_sec = cfg.cycle_deadline
        self.ibkr._deadline = self._cycle_deadline or (time.time() + cycle_deadline_sec)

        effective_initial_cash = initial_cash if initial_cash is not None else self._initial_cash

        logger.info(f"=== Starting Execution Engine (Step 3) ===")
        logger.info(f"Paper account: {self.paper_account}")

        # Step 1: Connect to IBKR
        connected = await self.ibkr.connect()
        logger.info(f"Connected: {connected}")

        # Step 2: Get portfolio state
        if initial_cash is not None:
            self.portfolio_tracker.set_cash(initial_cash)
            equity = initial_cash
        elif connected:
            account_info = await self.ibkr.get_account_info()
            equity = account_info.get("equity", effective_initial_cash)
            self.portfolio_tracker.set_cash(account_info.get("cash", effective_initial_cash))
            for symbol, qty in account_info.get("positions", {}).items():
                self.portfolio_tracker.positions[symbol] = qty
        else:
            logger.info(f"Using initial cash: {effective_initial_cash}")
            self.portfolio_tracker.set_cash(effective_initial_cash)
            equity = effective_initial_cash

        # Step 3: Build orders
        orders = self.order_builder.build_orders(signals, current_prices or {})
        logger.info(f"Built {len(orders)} orders")

        # Step 4: Execute orders
        fills = {}
        errors = []
        for order in orders:
            fill = await self._execute_order(order, current_prices or {})
            if fill:
                fills[order.symbol] = fill
                self._update_portfolio_after_fill(order, fill)
            else:
                errors.append(f"Order for {order.symbol} returned no fill")

        result = ExecutionResult(
            orders=orders,
            fills=fills,
            errors=errors,
        )
        result.portfolio_state = self.portfolio_tracker.get_state(current_prices)
        return result

    async def _execute_order(
        self,
        order: ExecutionOrder,
        current_prices: dict[str, float],
    ) -> Optional[dict[str, Any]]:
        """Execute a single order.

        Args:
            order: The execution order.
            current_prices: Dict mapping symbol to current price.

        Returns:
            Fill dict on success, None on failure.
        """
        price = current_prices.get(order.symbol, 0.0)
        if price <= 0:
            price = await self._get_current_price(order.symbol)
            if price <= 0:
                logger.warning(f"No price for {order.symbol}, skipping")
                return None

        fill = await self.ibkr.place_order(
            symbol=order.symbol,
            quantity=order.quantity,
            side=order.side,
            order_type=order.order_type,
            tif=order.tif,
        )

        if fill and fill.get("status") not in ("failed",):
            fill["fill_price"] = price
            logger.info(
                f"Filled: {order.side} {order.quantity} {order.symbol} @ {price:.2f}"
            )

        return fill

    async def _get_current_price(self, symbol: str) -> float:
        """Get current price for a symbol from Alpaca or IBKR.

        Args:
            symbol: Stock ticker symbol.

        Returns:
            Current price per share, or 0 on failure.
        """
        try:
            quote = self.ibkr.get_realtime_quote(symbol)
            return quote.get("last_price", 0)
        except Exception:
            pass
        return 0

    def _update_portfolio_after_fill(
        self,
        order: ExecutionOrder,
        fill: dict[str, Any],
    ) -> None:
        """Apply an order fill to the portfolio tracker.

        Uses the order's idempotent apply() method.

        Args:
            order: The execution order.
            fill: Fill result from the IBKR client.
        """
        fill_price = fill.get("fill_price", 0.0)
        if fill_price <= 0:
            return

        order.apply(self.portfolio_tracker, fill_price)

    async def execute_sells_first(
        self,
        signals: list[Any],
        current_prices: dict[str, float],
        initial_cash: float,
    ) -> ExecutionResult:
        """Execute with explicit sells-first enforcement.

        This is a convenience method that ensures all sell signals
        are processed before any buy signals, with dynamic portfolio
        balance updates between each.

        Args:
            signals: List of TechnicalSignal objects.
            current_prices: Dict mapping symbol to current price.
            initial_cash: Starting cash balance.

        Returns:
            ExecutionResult with fills and portfolio state.
        """
        # Set the shared deadline for all IBKR retries in this cycle
        cfg = load_config()
        self.ibkr._deadline = self._cycle_deadline or (time.time() + cfg.cycle_deadline)

        # Separate sells and buys
        sells = [s for s in signals if s.direction == "sell"]
        buys = [s for s in signals if s.direction == "buy"]

        # Deduplicate
        self.order_builder._processed_signals.clear()

        result = ExecutionResult()

        # Process sells first
        for signal in sells:
            price = current_prices.get(signal.symbol, 0.0)
            if price <= 0:
                continue

            quantity = self.order_builder.calculate_quantity(
                signal.symbol, "sell", signal.confidence, price,
                current_prices,
            )

            order = ExecutionOrder(
                symbol=signal.symbol,
                side="sell",
                quantity=quantity,
                order_type=self.order_type,
                tif="DAY",
                confidence=signal.confidence,
                reasoning=signal.reasoning,
            )

            result.orders.append(order)

            # Execute sell
            fill = await self.ibkr.place_order(
                symbol=signal.symbol,
                quantity=quantity,
                side="sell",
                order_type=self.order_type,
                tif="DAY",
            )

            if fill and fill.get("status") not in ("failed", "deadline"):
                fill["fill_price"] = price
                result.fills[signal.symbol] = fill
                order.apply(self.portfolio_tracker, price)
            else:
                result.errors.append(
                    f"Sell failed for {signal.symbol}: {fill.get('message', 'unknown')}"
                )

        # Then process buys with updated cash
        for signal in buys:
            # Check dedup
            if self.order_builder.is_duplicate(signal.symbol, "buy"):
                continue

            price = current_prices.get(signal.symbol, 0.0)
            if price <= 0:
                continue

            quantity = self.order_builder.calculate_quantity(
                signal.symbol, "buy", signal.confidence, price,
                current_prices,
            )

            if quantity < 1:
                continue

            order = ExecutionOrder(
                symbol=signal.symbol,
                side="buy",
                quantity=quantity,
                order_type=self.order_type,
                tif="DAY",
                confidence=signal.confidence,
                reasoning=signal.reasoning,
            )

            result.orders.append(order)

            # Execute buy
            fill = await self.ibkr.place_order(
                symbol=signal.symbol,
                quantity=quantity,
                side="buy",
                order_type=self.order_type,
                tif="DAY",
            )

            if fill and fill.get("status") not in ("failed", "deadline"):
                fill["fill_price"] = price
                result.fills[signal.symbol] = fill
                order.apply(self.portfolio_tracker, price)
            else:
                result.errors.append(
                    f"Buy failed for {signal.symbol}: {fill.get('message', 'unknown')}"
                )

        result.portfolio_state = self.portfolio_tracker.get_state(current_prices)
        return result
