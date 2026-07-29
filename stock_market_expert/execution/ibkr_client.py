"""IBKR client for paper trading via ib_insync.

Manages the connection to Interactive Brokers TWS/Gateway and provides
order execution capabilities for paper accounts.
"""

import logging
from typing import Any, Optional

from stock_market_expert.config.loader import load_config
from stock_market_expert.errors.handler import log_error

logger = logging.getLogger(__name__)


class IBKRClient:
    """Client for Interactive Brokers paper trading via ib_insync.

    Handles connection lifecycle, account info fetching, and order placement.
    All operations are no-op when the connection is unavailable (paper mode).
    """

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        account_id: Optional[str] = None,
        paper_account: bool = True,
    ):
        """Initialize the IBKR client.

        Args:
            host: TWS/Gateway host. Defaults to config ibkr_insync_host.
            port: TWS/Gateway port. Defaults to config ibkr_insync_port.
            account_id: IBKR account ID. Defaults to config ibkr_account_id.
            paper_account: Whether to use paper trading mode.
        """
        _config = None
        if (
            host is None
            or port is None
            or account_id is None
        ):
            _config = load_config()

        self.host = host or getattr(_config, "ibkr_insync_host", "localhost")
        self.port = port or getattr(_config, "ibkr_insync_port", 7497)
        self.account_id = account_id or getattr(_config, "ibkr_account_id", "")
        self.paper_account = paper_account
        self._connected = False
        self._api = None
        self._account_balance: dict[str, float] = {}
        self._positions: dict[str, float] = {}

    async def connect(self) -> bool:
        """Connect to IBKR TWS/Gateway.

        Returns:
            True if connection succeeded or paper mode is enabled without live connection.
        """
        try:
            from ib_insync import IB

            self._api = IB()
            self._api.connect(self.host, self.port, clientId=1)
            self._connected = True
            logger.info(f"Connected to IBKR at {self.host}:{self.port}")
            await self._refresh_account_info()
            return True
        except Exception as e:
            if self.paper_account:
                logger.warning(
                    f"IBKR connection failed ({e}). Running in offline paper mode."
                )
                self._connected = False
                return False
            log_error(e, "IBKR connection failed", "step3")
            raise

    async def disconnect(self) -> None:
        """Disconnect from IBKR TWS/Gateway."""
        if self._api is not None:
            try:
                self._api.disconnect()
            except Exception as e:
                log_error(e, "IBKR disconnect failed", "step3")
            self._connected = False
            logger.info("Disconnected from IBKR")

    async def _refresh_account_info(self) -> None:
        """Fetch current account balance and positions from IBKR."""
        if not self._connected or self._api is None:
            return

        try:
            account = self._api.accountValues()
            if account:
                for val in account:
                    if val.tag == "NetLiquidation":
                        self._account_balance["equity"] = float(val.value)
                    elif val.tag == "AvailableFunds":
                        self._account_balance["cash"] = float(val.value)

            positions = self._api.positions()
            for pos in positions:
                symbol = pos.contract.symbol
                self._positions[symbol] = float(pos.position)
        except Exception as e:
            log_error(e, "Failed to refresh account info", "step3")

    async def get_account_info(self) -> dict[str, Any]:
        """Get current account information.

        Returns:
            Dict with keys: equity, cash, positions, connected.
        """
        if self._connected and self._api is not None:
            await self._refresh_account_info()

        return {
            "equity": self._account_balance.get("equity", 0.0),
            "cash": self._account_balance.get("cash", 0.0),
            "positions": dict(self._positions),
            "connected": self._connected,
            "paper_account": self.paper_account,
        }

    async def get_portfolio_balance(self) -> dict[str, Any]:
        """Get current portfolio balance.

        Returns:
            Dict with cash and equity values.
        """
        info = await self.get_account_info()
        return {
            "cash": info["cash"],
            "equity": info["equity"],
        }

    async def get_positions(self) -> dict[str, float]:
        """Get current positions.

        Returns:
            Dict mapping symbol to quantity.
        """
        info = await self.get_account_info()
        return dict(info["positions"])

    async def place_order(
        self,
        symbol: str,
        quantity: int,
        side: str,
        order_type: str = "MKT",
        tif: str = "DAY",
    ) -> Optional[dict[str, Any]]:
        """Place an order via IBKR.

        Args:
            symbol: Stock ticker symbol.
            quantity: Number of shares.
            side: "buy" or "sell".
            order_type: Order type — "MKT" (market), "LMT" (limit).
            tif: Time-in-force — "DAY" for day orders.

        Returns:
            Order result dict on success, None on failure.
        """
        if not self._connected or self._api is None:
            logger.warning(
                f"Cannot place order for {symbol}: not connected. "
                f"Order would be: {side} {quantity} {symbol} {order_type} {tif}"
            )
            return {
                "symbol": symbol,
                "quantity": quantity,
                "side": side,
                "order_type": order_type,
                "tif": tif,
                "status": "simulated",
                "message": "Paper mode — order simulated",
            }

        try:
            from ib_insync import Order

            ib_order = Order(
                action="BUY" if side == "buy" else "SELL",
                totalQuantity=abs(quantity),
                orderType=order_type,
                tif=tif,
            )

            # For paper trading, we need a contract
            from ib_insync import Stock

            contract = Stock(symbol, "SMART", "USD")
            trade = self._api.placeOrder(contract, ib_order)

            # Wait for fill
            self._api.waitOnUpdate(timeout=10)

            result = {
                "symbol": symbol,
                "quantity": quantity,
                "side": side,
                "order_type": order_type,
                "tif": tif,
                "status": trade.orderStatus.status if trade else "pending",
                "filled": getattr(trade.orderStatus, "filled", 0),
            }
            logger.info(f"Order placed: {result}")
            return result

        except Exception as e:
            log_error(e, f"Failed to place order for {symbol}", "step3")
            return {
                "symbol": symbol,
                "quantity": quantity,
                "side": side,
                "order_type": order_type,
                "tif": tif,
                "status": "failed",
                "message": str(e),
            }
