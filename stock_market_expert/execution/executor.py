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

import asyncio
import logging
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
    ):
        """Initialize the execution engine.

        Args:
            ibkr_client: IBKR client instance.
            order_builder: Order builder instance.
            portfolio_tracker: Portfolio tracker instance.
            paper_account: Whether to use paper trading mode.
        """
        self.ibkr = ibkr_client or IBKRClient(paper_account=paper_account)
        self.order_builder = order_builder or OrderBuilder()
        self.portfolio_tracker = portfolio_tracker or PortfolioTracker()
        self.paper_account = paper_account

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
        logger.info(f"=== Starting Execution Engine (Step 3) ===")
        logger.info(f"Paper account: {self.paper_account}")

        # Step 1: Connect to IBKR
        connected = await self.ibkr.connect()
        logger.info(f"Connected: {connected}")

        # Step 2: Get portfolio state
        if initial_cash is not None:
            self.portfolio_tracker.set_cash(initial_cash)
            equity = initial_cash
            positions = {}
        else:
            account_info = await self.ibkr.get_account_info()
            equity = account_info.get("equity", 0.0)
            positions = account_info.get("positions", {})
            self.portfolio_tracker.set_cash(account_info.get("cash", 0.0))

        logger.info(f"Equity: {equity:.2f}, Cash: {self.portfolio_tracker.cash:.2f}")

        # Set portfolio state on order builder
        self.order_builder.set_portfolio(self.portfolio_tracker.cash, positions)

        # Step 3: Build orders with sells-first ordering
        prices = current_prices or {}
        orders = self.order_builder.build_orders(signals, prices, equity)

        if not orders:
            logger.info("No orders to execute.")
            return ExecutionResult(
                portfolio_state=self.portfolio_tracker.get_state(prices),
            )

        # Step 4: Execute orders — sells first, then buys
        fills = {}
        errors = []

        for order in orders:
            fill = await self._execute_order(order, prices)
            if fill and fill.get("status") != "failed":
                fills[order.symbol] = fill
                # Update portfolio after each order
                self._update_portfolio_after_fill(order, fill)
            else:
                error_msg = fill.get("message", "Unknown error") if fill else "No fill data"
                errors.append(f"Failed to fill {order.side} {order.quantity} {order.symbol}: {error_msg}")
                logger.error(f"Order failed: {order.side} {order.quantity} {order.symbol} — {error_msg}")

        # Step 5: Get final portfolio state
        portfolio_state = self.portfolio_tracker.get_state(prices)

        # Disconnect
        await self.ibkr.disconnect()

        result = ExecutionResult(
            orders=orders,
            fills=fills,
            portfolio_state=portfolio_state,
            errors=errors,
        )

        logger.info(
            f"=== Execution Complete: {len(fills)} filled, {len(errors)} errors ==="
        )
        return result

    async def _execute_order(
        self,
        order: ExecutionOrder,
        current_prices: dict[str, float],
    ) -> Optional[dict[str, Any]]:
        """Execute a single order.

        Args:
            order: The execution order to place.
            current_prices: Current market prices for fallback.

        Returns:
            Fill result dict, or None on failure.
        """
        price = current_prices.get(order.symbol, 0.0)

        if self.paper_account and price <= 0:
            # Paper mode with no price data — simulate at a default price
            logger.info(f"Simulating {order.side} order for {order.symbol}")
            return {
                "symbol": order.symbol,
                "side": order.side,
                "quantity": order.quantity,
                "fill_price": 100.0,
                "status": "filled",
                "message": "Simulated paper fill",
            }

        if price <= 0:
            logger.warning(f"No price for {order.symbol}, cannot execute")
            return {"status": "failed", "message": f"No price for {order.symbol}"}

        # Place the order via IBKR
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

    def _update_portfolio_after_fill(
        self,
        order: ExecutionOrder,
        fill: dict[str, Any],
    ) -> None:
        """Update portfolio tracker after an order fill.

        Args:
            order: The execution order.
            fill: Fill result from the IBKR client.
        """
        fill_price = fill.get("fill_price", 0.0)
        if fill_price <= 0:
            return

        if order.side == "sell":
            self.portfolio_tracker.update_after_sell(
                order.symbol, order.quantity, fill_price
            )
        else:
            self.portfolio_tracker.update_after_buy(
                order.symbol, order.quantity, fill_price
            )

        # Update order builder state
        self.order_builder.apply_order(order, fill_price)

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
                signal.symbol, "sell", signal.confidence, price
            )

            order = ExecutionOrder(
                symbol=signal.symbol,
                side="sell",
                quantity=quantity,
                order_type="MKT",
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
                order_type="MKT",
                tif="DAY",
            )

            if fill and fill.get("status") != "failed":
                fill["fill_price"] = price
                result.fills[signal.symbol] = fill
                self.portfolio_tracker.update_after_sell(
                    signal.symbol, quantity, price
                )
                self.order_builder.apply_order(order, price)
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
                signal.symbol, "buy", signal.confidence, price
            )

            if quantity < 1:
                continue

            order = ExecutionOrder(
                symbol=signal.symbol,
                side="buy",
                quantity=quantity,
                order_type="MKT",
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
                order_type="MKT",
                tif="DAY",
            )

            if fill and fill.get("status") != "failed":
                fill["fill_price"] = price
                result.fills[signal.symbol] = fill
                self.portfolio_tracker.update_after_buy(
                    signal.symbol, quantity, price
                )
                self.order_builder.apply_order(order, price)
            else:
                result.errors.append(
                    f"Buy failed for {signal.symbol}: {fill.get('message', 'unknown')}"
                )

        result.portfolio_state = self.portfolio_tracker.get_state(current_prices)
        return result
