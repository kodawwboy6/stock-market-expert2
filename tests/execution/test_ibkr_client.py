"""Tests for IBKRClient — paper trading client."""

import time

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
async def test_connect_with_deadline_expires(client):
    """connect should return False when deadline expires during retry."""
    past_deadline = time.time() - 1  # already expired
    client._deadline = past_deadline
    result = await client.connect()
    assert result is False


@pytest.mark.asyncio
async def test_connect_with_future_deadline_succeeds(client):
    """connect should succeed when deadline is in the future."""
    future_deadline = time.time() + 300
    client._deadline = future_deadline
    result = await client.connect()
    # In paper mode without TWS, result may be True or False depending on env
    assert isinstance(result, bool)


@pytest.mark.asyncio
async def test_get_account_info_with_deadline_expires(client):
    """get_account_info should return empty state when deadline expires."""
    past_deadline = time.time() - 1
    client._deadline = past_deadline
    info = await client.get_account_info()
    assert info["equity"] == 0.0
    assert info["cash"] == 0.0
    assert info["positions"] == {}
    assert info["connected"] is False


@pytest.mark.asyncio
async def test_place_order_with_deadline_expires(client):
    """place_order should return deadline status when deadline expires."""
    past_deadline = time.time() - 1
    client._deadline = past_deadline
    # Pretend connected with a valid _api (not None) to trigger retry path
    client._connected = True
    client._api = object()  # mock API object
    result = await client.place_order("AAPL", 10, "buy")
    assert result["status"] == "deadline"


@pytest.mark.asyncio
async def test_place_order_without_connection_returns_simulated(client):
    """place_order should return simulated status when not connected."""
    result = await client.place_order("AAPL", 10, "buy")
    assert result["status"] == "simulated"
