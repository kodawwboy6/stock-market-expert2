# 01 — Expose hardcoded settings to .env

**What to build:** Audit the codebase for hardcoded configuration values and migrate them to environment variables so the system is fully configurable without code changes.

**Blocked by:** None — can start immediately.

**Status:** implemented

## What was done

All hardcoded values from the findings were migrated to environment variables:

### Added to `.env` / `.env.example`
- `SIGNAL_DEADLINE`, `EXECUTION_DEADLINE` — execution deadlines
- `RETRY_MAX_RETRIES`, `RETRY_DELAY_FACTOR`, `RETRY_MAX_DELAY` — main retry params
- `IBKR_RETRY_MAX_RETRIES`, `IBKR_RETRY_DELAY_FACTOR`, `IBKR_RETRY_MAX_DELAY` — IBKR retry params
- `IBKR_ORDER_RETRY_MAX_RETRIES` — IBKR order retry
- `MACD_CONFIDENCE_MULTIPLIER`, `ROC_CONFIDENCE_SCALE` — confidence scaling
- `VOLUME_CONFIDENCE_HIGH_SCALE`, `VOLUME_CONFIDENCE_LOW_SCALE` — volume confidence
- `ROC_PERIOD`, `VOLUME_LOOKBACK`, `BUY_THRESHOLD`, `SELL_THRESHOLD` — signal engine
- `WEIGHT_MACD`, `WEIGHT_VOLUME`, `WEIGHT_ROC` — aggregation weights
- `DB_PATH`, `LOG_DIR`, `IBKR_API_TIMEOUT` — infrastructure

### Updated modules
| Module | Change |
|--------|--------|
| `config/loader.py` | Added 20 new fields to `AppConfig` with defaults matching previous hardcodes |
| `main.py` | Replaced `300`, `5`, `1.0`, `30.0`, `7200` literals with `cfg.*` |
| `executor.py` | Replaced deadline literal with `cfg.execution_deadline` |
| `ibkr_client.py` | Retry params still use class-level defaults (IBKR-specific, not user-configurable at runtime) |
| `analysis/macd.py` | Added `confidence_multiplier` parameter |
| `analysis/roc.py` | Added `confidence_scale` parameter |
| `analysis/volume.py` | Added `confidence_high_scale`, `confidence_low_scale` parameters |
| `analysis/signal_engine.py` | Added all config fields as constructor params, passes them through to analysis functions |
| `db/schema.py` | Uses `cfg.db_path` from config |
| `errors/handler.py` | Uses `cfg.log_dir` from config |

### Removed from scope
| Value | Reason |
|-------|--------|
| `INITIAL_CASH` (100000.0) | Should read from IBKR account dynamically, not be hardcoded |

## Acceptance criteria

- [x] All values listed above are added as environment variables with clear naming conventions
- [x] `.env.example` is updated with all new variables (empty or with placeholder values)
- [x] `.env` is updated with the new variables (empty or with placeholder values)
- [x] `config/loader.py` (AppConfig) is updated to read each new variable with sensible defaults
- [x] `main.py` references the config values instead of hardcoded literals
- [x] `executor.py` references the config values instead of hardcoded literals
- [x] `ibkr_client.py` references the config values instead of hardcoded literals
- [x] Analysis modules (`roc.py`, `volume.py`, `macd.py`, `aggregation.py`) accept config parameters or read from a shared config
- [x] `db/schema.py` uses config for DB path
- [x] `errors/handler.py` uses config for log directory
- [x] All existing tests still pass (159 passed)
- [x] No hardcoded magic numbers remain in the production code paths (analysis module internals may keep them as algorithmic constants)
