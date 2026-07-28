-- Signal history table
-- Stores all generated signals for deduplication and audit trail.
CREATE TABLE IF NOT EXISTS signal_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    direction TEXT NOT NULL CHECK(direction IN ('buy', 'sell', 'short')),
    confidence REAL NOT NULL,
    weighted_score REAL NOT NULL,
    macd_value REAL,
    roc_value REAL,
    volume_ratio REAL,
    source TEXT NOT NULL DEFAULT 'technical',
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'utc')),
    UNIQUE(symbol, direction, created_at)
);

-- Trade history table
-- Stores all executed trades for audit and performance tracking.
CREATE TABLE IF NOT EXISTS trade_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    direction TEXT NOT NULL CHECK(direction IN ('buy', 'sell', 'short')),
    quantity REAL NOT NULL,
    price REAL NOT NULL,
    order_id TEXT,
    confidence REAL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'filled', 'cancelled', 'failed')),
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'utc')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now', 'utc'))
);
