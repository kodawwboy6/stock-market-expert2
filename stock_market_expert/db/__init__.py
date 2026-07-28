"""Database module for the stock market expert system.

Provides SQLite persistence for signal history and trade history.
"""

from stock_market_expert.db.schema import init_db, get_connection

__all__ = ["init_db", "get_connection"]
