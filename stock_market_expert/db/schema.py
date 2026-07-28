"""Database schema initialization and connection management.

Reads the SQL schema file and creates tables if they don't exist.
Provides a connection factory for SQLite access.
"""

import sqlite3
from pathlib import Path

_DB_PATH = Path("data/stock_market_expert.db")
_SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def init_db(db_path: Path | None = None) -> Path:
    """Initialize the database by creating tables from schema.sql.

    Args:
        db_path: Path to the SQLite database file. Defaults to data/stock_market_expert.db.

    Returns:
        The path to the initialized database file.
    """
    db_path = db_path or _DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with open(_SCHEMA_PATH) as f:
        schema_sql = f.read()

    conn = sqlite3.connect(str(db_path))
    try:
        conn.executescript(schema_sql)
        conn.commit()
    finally:
        conn.close()

    return db_path


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """Get a new SQLite connection.

    Args:
        db_path: Path to the SQLite database file. Defaults to data/stock_market_expert.db.

    Returns:
        A sqlite3.Connection instance.
    """
    db_path = db_path or _DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(str(db_path))
