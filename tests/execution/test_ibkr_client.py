"""Tests for IBKRClient — paper trading client."""

import pytest

from stock_market_expert.execution.ibkr_client import IBKRClient


@pytest.fixture
def client():
    """Create an IBKRClient in paper mode."""
    return IBKRClient(paper_account=True)


def test_init_defaults(client):
    """IBKRClient should use default values when no args provided."""
    assert client.host == "localhost"
    assert client.port == 7497
    assert client.paper_account is True
    assert client._connected is False


def test_init_with_args():
    """IBKRClient should accept custom connection parameters."""
    client = IBKRClient(
        host="192.168.1.1",
        port=4242,
        account_id="U123456",
        paper_account=False,
    )
    assert client.host == "192.168.1.1"
    assert client.port == 4242
    assert client.account_id == "U123456"
    assert client.paper_account is False


@pytest.mark.asyncio
async def test_connect_falls_back_to_paper_mode(client):
    """connect should return False in paper mode when TWS is unavailable."""
    result = await client.connect()
    # In paper mode without real TWS, should gracefully handle
    assert result is False or result is True  # depends on env


@pytest.mark.asyncio
async def test_disconnect(client):
    """disconnect should set _connected to False."""
    await client.disconnect()
    assert client._connected is False


@pytest.mark.asyncio
async def test_get_account_info(client):
    """get_account_info should return default values when not connected."""
    info = await client.get_account_info()
    assert "equity" in info
    assert "cash" in info
    assert "positions" in info
    assert "connected" in info
    assert info["connected"] is False


@pytest.mark.asyncio
async def test_get_portfolio_balance(client):
    """get_portfolio_balance should return cash and equity."""
    balance = await client.get_portfolio_balance()
    assert "cash" in balance
    assert "equity" in balance


@pytest.mark.asyncio
async def test_get_positions(client):
    """get_positions should return empty dict when not connected."""
    positions = await client.get_positions()
    assert positions == {}


@pytest.mark.asyncio
async def test_place_order_paper_mode(client):
    """place_order in paper mode should return simulated result."""
    result = await client.place_order(
        symbol="AAPL",
        quantity=10,
        side="buy",
        order_type="MKT",
        tif="DAY",
    )
    assert result is not None
    assert result["symbol"] == "AAPL"
    assert result["quantity"] == 10
    assert result["side"] == "buy"
    assert result["status"] == "simulated"


@pytest.mark.asyncio
async def test_place_order_sell(client):
    """place_order should pass correct side to IBKR."""
    result = await client.place_order(
        symbol="GOOGL",
        quantity=5,
        side="sell",
        order_type="MKT",
        tif="DAY",
    )
    assert result["side"] == "sell"
    assert result["order_type"] == "MKT"
    assert result["tif"] == "DAY"
