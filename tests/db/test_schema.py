"""Tests for the db/schema module."""

import sqlite3
from pathlib import Path

from stock_market_expert.db.schema import init_db, get_connection


class TestInitDb:
    """Tests for the init_db function."""

    def test_creates_database_file(self, tmp_path):
        """init_db should create the database file."""
        db_path = tmp_path / "test.db"
        assert not db_path.exists()

        result = init_db(db_path)

        assert result == db_path
        assert db_path.exists()

    def test_creates_signal_history_table(self, tmp_path):
        """init_db should create the signal_history table."""
        db_path = tmp_path / "test.db"
        init_db(db_path)

        conn = sqlite3.connect(str(db_path))
        try:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='signal_history'"
            )
            assert cursor.fetchone() is not None
        finally:
            conn.close()

    def test_creates_trade_history_table(self, tmp_path):
        """init_db should create the trade_history table."""
        db_path = tmp_path / "test.db"
        init_db(db_path)

        conn = sqlite3.connect(str(db_path))
        try:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='trade_history'"
            )
            assert cursor.fetchone() is not None
        finally:
            conn.close()

    def test_signal_history_columns(self, tmp_path):
        """signal_history should have the correct columns."""
        db_path = tmp_path / "test.db"
        init_db(db_path)

        conn = sqlite3.connect(str(db_path))
        try:
            cursor = conn.execute("PRAGMA table_info(signal_history)")
            columns = {row[1] for row in cursor.fetchall()}
            expected = {
                "id", "symbol", "direction", "confidence",
                "weighted_score", "macd_value", "roc_value",
                "volume_ratio", "source", "created_at",
            }
            assert expected.issubset(columns)
        finally:
            conn.close()

    def test_trade_history_columns(self, tmp_path):
        """trade_history should have the correct columns."""
        db_path = tmp_path / "test.db"
        init_db(db_path)

        conn = sqlite3.connect(str(db_path))
        try:
            cursor = conn.execute("PRAGMA table_info(trade_history)")
            columns = {row[1] for row in cursor.fetchall()}
            expected = {
                "id", "symbol", "direction", "quantity",
                "price", "order_id", "confidence",
                "status", "created_at", "updated_at",
            }
            assert expected.issubset(columns)
        finally:
            conn.close()

    def test_creates_data_dir(self, tmp_path):
        """init_db should create the data directory if it doesn't exist."""
        db_path = tmp_path / "subdir" / "test.db"
        assert not db_path.parent.exists()

        init_db(db_path)

        assert db_path.parent.exists()


class TestGetConnection:
    """Tests for the get_connection function."""

    def test_returns_connection(self, tmp_path):
        """get_connection should return a sqlite3.Connection."""
        db_path = tmp_path / "test.db"
        init_db(db_path)

        conn = get_connection(db_path)
        assert isinstance(conn, sqlite3.Connection)
        conn.close()

    def test_connection_works(self, tmp_path):
        """Connection should be usable for queries."""
        db_path = tmp_path / "test.db"
        init_db(db_path)

        conn = get_connection(db_path)
        cursor = conn.execute("SELECT count(*) FROM sqlite_master")
        assert cursor.fetchone()[0] > 0
        conn.close()
