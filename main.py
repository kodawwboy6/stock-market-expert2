#!/usr/bin/env python3
"""Stock Market Expert — Orchestrator entry point.

Runs the full pipeline in a continuous loop:
  Step 1 (News Analysis) -> Step 2 (Signal Generation) -> Step 3 (Execution)

Configurable via .env:
  EXECUTION_INTERVAL    — seconds between cycles (default: 7200 / 2 hours)
  RUN_MODE              — "continuous" or "once" (default: "continuous")
  LOG_LEVEL             — logging level (default: "INFO")
"""

import asyncio
import logging
import signal
import sys
import time
from datetime import datetime, timezone
from typing import Optional

from stock_market_expert.config.loader import load_config
from stock_market_expert.core.pipeline import NewsPipeline, NewsPipelineResult
from stock_market_expert.analysis.signal_engine import SignalEngine, TechnicalSignal
from stock_market_expert.execution.executor import ExecutionEngine, ExecutionResult
from stock_market_expert.db.schema import init_db
from stock_market_expert.utils.logger import get_logger
from stock_market_expert.errors.handler import (
    async_retry_with_backoff,
    DeadlineExceededError,
)


# ── Globals for graceful shutdown ──────────────────────────────────────

_shutdown = False
config = None  # AppConfig — loaded in main()
logger: logging.Logger = logging.getLogger("stock_market_expert")  # default logger


def _get_logger() -> logging.Logger:
    """Return the configured logger, initializing if needed."""
    global logger
    if not logger.handlers:
        log_level = "INFO"
        if config is not None:
            try:
                log_level = config.log_level or "INFO"
            except AttributeError:
                pass
        logger = get_logger(name="stock_market_expert", level=log_level)
    return logger


def _handle_signal(signum: int, _frame: Optional[object]) -> None:
    global _shutdown
    _shutdown = True


signal.signal(signal.SIGINT, _handle_signal)
signal.signal(signal.SIGTERM, _handle_signal)


# ── Cycle functions ───────────────────────────────────────────────────

async def run_step1(cfg: object) -> NewsPipelineResult:
    """Execute Step 1: News Analysis.

    Returns the news pipeline result (active sectors, catalysts, operations).
    On persistent failure, returns an empty result so the pipeline can continue.
    """
    try:
        pipeline = NewsPipeline(
            api_key=cfg.alpha_vantage_api_key,
            finnhub_api_key=cfg.finnhub_api_key,
            lm_studio_base_url=cfg.lm_studio_base_url,
            lm_studio_model=cfg.lm_studio_model,
            news_category=cfg.news_category,
            max_news_items=cfg.news_max_items,
            confidence_threshold=cfg.news_confidence_threshold,
        )
        return pipeline.run()
    except Exception as exc:
        _get_logger().error(f"Step 1 failed: {exc}")
        return NewsPipelineResult(
            active_sectors=[],
            catalysts=[],
            operations=[],
            news_count=0,
            company_news_count=0,
            fallback_used=True,
            date_used=datetime.now(timezone.utc).isoformat(),
        )


async def run_step2(
    symbols: list[str],
    cfg: object,
) -> list[TechnicalSignal]:
    """Execute Step 2: Signal Generation with retry.

    Retries with backoff until success or deadline expires.
    """
    deadline = time.time() + 300  # 5-minute deadline for signal generation

    async def _try_signals() -> list[TechnicalSignal]:
        engine = SignalEngine(
            twelve_data_key=cfg.twelve_data_api_key,
            alpaca_api_key=cfg.alpaca_api_key,
            alpaca_secret_key=cfg.alpaca_secret_key,
            alpaca_base_url=cfg.alpaca_base_url,
            history_days=cfg.history_days,
            macd_fast=cfg.macd_fast,
            macd_slow=cfg.macd_slow,
            macd_signal=cfg.macd_signal,
            roc_period=10,
            volume_lookback=20,
            buy_threshold=0.3,
            sell_threshold=-0.3,
            min_confidence=cfg.min_signal_confidence,
        )
        engine.reset_dedup()
        return engine.generate_signals(symbols)

    try:
        return await async_retry_with_backoff(
            _try_signals,
            max_retries=5,
            delay_factor=1.0,
            max_delay=30.0,
            deadline=deadline,
        )
    except DeadlineExceededError:
        _get_logger().warning("Step 2 deadline exceeded — skipping cycle")
        return []
    except Exception as exc:
        _get_logger().error(f"Step 2 failed after retries: {exc}")
        return []


async def run_step3(
    signals: list[TechnicalSignal],
    cfg: object,
) -> ExecutionResult:
    """Execute Step 3: Order Execution with retry.

    Retries with backoff until success or deadline expires.
    """
    if not signals:
        return ExecutionResult()

    deadline = time.time() + 600  # 10-minute deadline for execution

    async def _try_execute() -> ExecutionResult:
        engine = ExecutionEngine(
            paper_account=cfg.paper_account,
            cycle_deadline=deadline,
        )
        initial_cash = 100000.0
        return await engine.run(signals, initial_cash=initial_cash)

    try:
        return await async_retry_with_backoff(
            _try_execute,
            max_retries=5,
            delay_factor=1.0,
            max_delay=30.0,
            deadline=deadline,
        )
    except DeadlineExceededError:
        _get_logger().warning("Step 3 deadline exceeded — skipping cycle")
        return ExecutionResult()
    except Exception as exc:
        _get_logger().error(f"Step 3 failed after retries: {exc}")
        return ExecutionResult()


# ── Cycle loop ────────────────────────────────────────────────────────

async def run_cycle() -> None:
    """Run one complete execution cycle (Step 1 -> Step 2 -> Step 3)."""
    log = _get_logger()
    cycle_start = datetime.now(timezone.utc)
    cycle_ts = cycle_start.isoformat()

    log.info(f"{'='*60}")
    log.info(f"Cycle started at {cycle_ts}")
    log.info(f"{'='*60}")

    # ── Step 1: News Analysis ───────────────────────────────────────
    log.info(">>> Step 1: News Analysis")
    news_result = await run_step1(config)

    if not news_result.active_sectors and not news_result.operations:
        log.warning("Step 1 produced no actionable results — skipping cycle")
        return

    # ── Step 2: Signal Generation ───────────────────────────────────
    log.info(">>> Step 2: Signal Generation")

    # Collect symbols from operations and active sectors
    symbols: set[str] = set()
    for op in news_result.operations:
        symbols.add(op.symbol)
    for sector in news_result.active_sectors:
        for s in sector.stocks:
            symbols.add(s)

    signals = await run_step2(list(symbols), config)
    log.info(f"Generated {len(signals)} signals")

    if not signals:
        log.warning("No signals generated — skipping execution")
        return

    # ── Step 3: Execution ───────────────────────────────────────────
    log.info(">>> Step 3: Execution")
    exec_result = await run_step3(signals, config)
    log.info(
        f"Executed {len(exec_result.orders)} orders, "
        f"{len(exec_result.fills)} fills, "
        f"{len(exec_result.errors)} errors"
    )

    # ── Persist signal history to SQLite ────────────────────────────
    _persist_signals(signals)

    cycle_end = datetime.now(timezone.utc)
    duration = (cycle_end - cycle_start).total_seconds()
    log.info(f"Cycle completed in {duration:.1f}s")
    log.info(f"{'='*60}")


def _persist_signals(signals: list[TechnicalSignal]) -> None:
    """Write signal history to SQLite for deduplication and audit."""
    from stock_market_expert.db.schema import get_connection

    conn = get_connection()
    try:
        for sig in signals:
            conn.execute(
                """INSERT OR IGNORE INTO signal_history
                   (symbol, direction, confidence, weighted_score, source)
                   VALUES (?, ?, ?, ?, 'orchestrator')""",
                (sig.symbol, sig.direction, sig.confidence, sig.score),
            )
        conn.commit()
    except Exception as exc:
        _get_logger().warning(f"Failed to persist signals: {exc}")
    finally:
        conn.close()


# ── Main ──────────────────────────────────────────────────────────────

def main() -> None:
    """Entry point: load config, initialize, and run the cycle loop."""
    global config

    # Load configuration
    config = load_config()

    # Initialize logger
    log_level = "INFO"
    try:
        log_level = config.log_level or "INFO"
    except AttributeError:
        pass

    logger = get_logger(
        name="stock_market_expert",
        level=log_level,
    )

    # Initialize database
    try:
        init_db()
        logger.info("Database initialized")
    except Exception as exc:
        logger.error(f"Database initialization failed: {exc}")
        sys.exit(1)

    # Determine interval and mode
    interval = 7200  # default 2 hours
    try:
        val = config.execution_interval
        if val is not None:
            interval = int(val)
    except (ValueError, TypeError, AttributeError):
        pass

    run_mode = "continuous"
    try:
        run_mode = config.run_mode
    except AttributeError:
        pass

    logger.info("Stock Market Expert starting")
    logger.info(f"Mode: {run_mode}, Interval: {interval}s")

    if run_mode == "once":
        logger.info("Running once mode — exiting after one cycle")
        asyncio.run(run_cycle())
        return

    # ── Continuous loop ─────────────────────────────────────────────
    logger.info(f"Entering continuous loop (interval: {interval}s)")
    while not _shutdown:
        try:
            asyncio.run(run_cycle())
        except Exception as exc:
            logger.error(f"Cycle error: {exc}")

        # Wait for next cycle (check shutdown periodically)
        remaining = interval
        while remaining > 0 and not _shutdown:
            time.sleep(min(1, remaining))
            remaining -= 1

    logger.info("Shutdown signal received — exiting")


if __name__ == "__main__":
    main()
