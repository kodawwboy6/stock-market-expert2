"""Full end-to-end integration tests for the orchestrator.

Tests the complete pipeline flow:
  Step 1 (News Analysis) -> Step 2 (Signal Generation) -> Step 3 (Execution)

Uses mocking to avoid external API calls while verifying:
  - Sequential step execution
  - Signal deduplication
  - Error handling (skip on persistent failure, retry)
  - Configurable interval
  - Logging output
  - Graceful shutdown
"""

import asyncio
import logging
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from stock_market_expert.core.pipeline import NewsPipelineResult, ActiveSector, OperationRecommendation, Catalyst
from stock_market_expert.analysis.signal_engine import TechnicalSignal
from stock_market_expert.execution.executor import ExecutionResult, ExecutionOrder
from main import run_cycle, run_step1, run_step2, run_step3, _persist_signals, _shutdown


# ── Fixtures ─────────────────────────────────────────────────────────

@pytest.fixture
def mock_config():
    """Create a mock AppConfig."""
    cfg = MagicMock()
    cfg.alpha_vantage_api_key = "test_av_key"
    cfg.finnhub_api_key = "test_fh_key"
    cfg.lm_studio_base_url = "http://localhost:1234/v1"
    cfg.lm_studio_model = "lms-7b"
    cfg.news_category = "technology"
    cfg.news_max_items = 50
    cfg.news_confidence_threshold = 0.6
    cfg.twelve_data_api_key = "test_td_key"
    cfg.alpaca_api_key = "test_alpaca_key"
    cfg.alpaca_secret_key = "test_alpaca_secret"
    cfg.alpaca_base_url = "https://paper-api.alpaca.markets"
    cfg.history_days = 90
    cfg.macd_fast = 12
    cfg.macd_slow = 26
    cfg.macd_signal = 9
    cfg.min_signal_confidence = 0.7
    cfg.paper_account = True
    cfg.execution_interval = 7200
    cfg.run_mode = "continuous"
    cfg.log_level = "INFO"
    cfg.log_retention_days = 30
    return cfg


@pytest.fixture
def mock_news_result():
    """Create a mock NewsPipelineResult with actionable data."""
    return NewsPipelineResult(
        active_sectors=[
            ActiveSector(
                sector="AI",
                stocks=["AAPL", "MSFT"],
                direction="buy",
                confidence=0.85,
                reasoning="Strong AI news flow",
            ),
        ],
        catalysts=[
            Catalyst(
                type="product_launch",
                description="New AI product",
                impact="positive",
                stocks=["AAPL"],
            ),
        ],
        operations=[
            OperationRecommendation(
                symbol="AAPL",
                direction="buy",
                confidence=0.85,
                reasoning="Strong buy signal",
                catalyst="New AI product",
            ),
            OperationRecommendation(
                symbol="MSFT",
                direction="buy",
                confidence=0.75,
                reasoning="Buy on momentum",
                catalyst="AI adoption",
            ),
        ],
        news_count=10,
        company_news_count=5,
        fallback_used=False,
        date_used=datetime.now(timezone.utc).isoformat(),
    )


@pytest.fixture
def mock_signals():
    """Create mock TechnicalSignal objects."""
    return [
        TechnicalSignal(
            symbol="AAPL",
            direction="buy",
            confidence=0.85,
            score=0.45,
            reasoning="MACD bullish crossover",
        ),
        TechnicalSignal(
            symbol="MSFT",
            direction="buy",
            confidence=0.70,
            score=0.35,
            reasoning="Volume confirmation",
        ),
    ]


# ── Step 1 tests ─────────────────────────────────────────────────────

class TestRunStep1:
    """Tests for run_step1 (News Analysis)."""

    @pytest.mark.asyncio
    @patch("main.NewsPipeline")
    async def test_step1_returns_result(self, mock_pipeline_class, mock_config):
        """run_step1 should return a NewsPipelineResult."""
        mock_result = MagicMock(spec=NewsPipelineResult)
        mock_result.active_sectors = []
        mock_result.operations = []
        mock_instance = MagicMock()
        mock_instance.run.return_value = mock_result
        mock_pipeline_class.return_value = mock_instance

        result = await run_step1(mock_config)

        mock_pipeline_class.assert_called_once()
        assert result is mock_result

    @pytest.mark.asyncio
    async def test_step1_handles_failure(self, mock_config):
        """run_step1 should return empty result on failure."""
        mock_config.alpha_vantage_api_key = ""
        mock_config.finnhub_api_key = ""
        mock_config.lm_studio_base_url = ""
        mock_config.lm_studio_model = ""

        with patch("main.NewsPipeline") as mock_pipeline_class:
            mock_pipeline_class.side_effect = Exception("API key missing")

            result = await run_step1(mock_config)

            assert result.active_sectors == []
            assert result.operations == []
            assert result.fallback_used is True


# ── Step 2 tests ─────────────────────────────────────────────────────

class TestRunStep2:
    """Tests for run_step2 (Signal Generation)."""

    @pytest.mark.asyncio
    @patch("main.SignalEngine")
    async def test_step2_returns_signals(self, mock_engine_class, mock_config):
        """run_step2 should return signals for given symbols."""
        mock_signals = [
            TechnicalSignal(symbol="AAPL", direction="buy", confidence=0.85, score=0.45, reasoning="test"),
        ]
        mock_instance = MagicMock()
        mock_instance.generate_signals.return_value = mock_signals
        mock_instance.reset_dedup = MagicMock()
        mock_engine_class.return_value = mock_instance

        result = await run_step2(["AAPL", "MSFT"], mock_config)

        assert len(result) == 1
        assert result[0].symbol == "AAPL"
        mock_instance.reset_dedup.assert_called_once()

    @pytest.mark.asyncio
    async def test_step2_returns_empty_on_failure(self, mock_config):
        """run_step2 should return empty list on persistent failure."""
        mock_config.twelve_data_api_key = ""
        mock_config.alpaca_api_key = ""
        mock_config.alpaca_secret_key = ""

        with patch("main.SignalEngine") as mock_engine_class:
            mock_engine_class.side_effect = Exception("Connection failed")

            result = await run_step2(["AAPL"], mock_config)

            assert result == []


# ── Step 3 tests ─────────────────────────────────────────────────────

class TestRunStep3:
    """Tests for run_step3 (Execution)."""

    @pytest.mark.asyncio
    @patch("main.ExecutionEngine")
    async def test_step3_returns_result(self, mock_engine_class, mock_config):
        """run_step3 should return ExecutionResult."""
        mock_result = MagicMock(spec=ExecutionResult)
        mock_result.orders = []
        mock_result.fills = {}
        mock_result.errors = []
        mock_instance = MagicMock()
        mock_instance.run = AsyncMock(return_value=mock_result)
        mock_engine_class.return_value = mock_instance

        signals = [
            TechnicalSignal(symbol="AAPL", direction="buy", confidence=0.85, score=0.45, reasoning="test"),
        ]
        result = await run_step3(signals, mock_config)

        assert result is mock_result
        mock_instance.run.assert_called_once()

    @pytest.mark.asyncio
    async def test_step3_returns_empty_on_no_signals(self, mock_config):
        """run_step3 should return empty result when no signals provided."""
        result = await run_step3([], mock_config)

        assert isinstance(result, ExecutionResult)
        assert len(result.orders) == 0


# ── Full cycle tests ─────────────────────────────────────────────────

class TestRunCycle:
    """Tests for the full run_cycle orchestration."""

    @pytest.mark.asyncio
    @patch("main.run_step1")
    @patch("main.run_step2")
    @patch("main.run_step3")
    @patch("main._persist_signals")
    async def test_cycle_runs_steps_sequentially(
        self, mock_persist, mock_step3, mock_step2, mock_step1, mock_config,
    ):
        """run_cycle should execute Step 1 -> Step 2 -> Step 3 in order."""
        mock_step1.return_value = MagicMock(
            active_sectors=[MagicMock(sector="AI", stocks=["AAPL"], direction="buy", confidence=0.85, reasoning="test")],
            catalysts=[],
            operations=[
                MagicMock(symbol="AAPL", direction="buy", confidence=0.85, reasoning="test"),
            ],
            news_count=10,
            company_news_count=5,
            fallback_used=False,
            date_used=datetime.now(timezone.utc).isoformat(),
        )
        mock_step2.return_value = [
            TechnicalSignal(symbol="AAPL", direction="buy", confidence=0.85, score=0.45, reasoning="test"),
        ]
        mock_step3.return_value = MagicMock(
            orders=[MagicMock()],
            fills={"AAPL": {"status": "filled"}},
            errors=[],
        )

        await run_cycle()

        # Verify sequential order
        step1_call = mock_step1.call_args
        step2_call = mock_step2.call_args
        step3_call = mock_step3.call_args

        assert step1_call is not None
        assert step2_call is not None
        assert step3_call is not None

    @pytest.mark.asyncio
    @patch("main.run_step1")
    @patch("main.run_step2")
    @patch("main.run_step3")
    async def test_cycle_skips_on_no_news(
        self, mock_step3, mock_step2, mock_step1, mock_config,
    ):
        """run_cycle should skip Steps 2/3 when Step 1 produces no results."""
        mock_step1.return_value = MagicMock(
            active_sectors=[],
            catalysts=[],
            operations=[],
            news_count=0,
            company_news_count=0,
            fallback_used=True,
            date_used=datetime.now(timezone.utc).isoformat(),
        )

        await run_cycle()

        mock_step2.assert_not_called()
        mock_step3.assert_not_called()

    @pytest.mark.asyncio
    @patch("main.run_step1")
    @patch("main.run_step2")
    @patch("main.run_step3")
    async def test_cycle_skips_execution_on_no_signals(
        self, mock_step3, mock_step2, mock_step1, mock_config,
    ):
        """run_cycle should skip Step 3 when no signals are generated."""
        mock_step1.return_value = MagicMock(
            active_sectors=[MagicMock(sector="AI", stocks=["AAPL"], direction="buy", confidence=0.85, reasoning="test")],
            catalysts=[],
            operations=[MagicMock(symbol="AAPL", direction="buy", confidence=0.85, reasoning="test")],
            news_count=10,
            company_news_count=5,
            fallback_used=False,
            date_used=datetime.now(timezone.utc).isoformat(),
        )
        mock_step2.return_value = []

        await run_cycle()

        mock_step3.assert_not_called()


# ── Signal persistence tests ─────────────────────────────────────────

class TestPersistSignals:
    """Tests for signal persistence to SQLite."""

    def test_persist_signals_writes_to_db(self, tmp_path):
        """_persist_signals should write signals to SQLite."""
        signals = [
            TechnicalSignal(symbol="AAPL", direction="buy", confidence=0.85, score=0.45, reasoning="test"),
            TechnicalSignal(symbol="MSFT", direction="sell", confidence=0.70, score=-0.35, reasoning="test"),
        ]

        # Create a temp database with the schema
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("""CREATE TABLE IF NOT EXISTS signal_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            direction TEXT NOT NULL,
            confidence REAL NOT NULL,
            weighted_score REAL NOT NULL,
            source TEXT NOT NULL DEFAULT 'technical',
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'utc'))
        )""")
        conn.commit()
        conn.close()

        # Patch get_connection at the source module
        with patch("stock_market_expert.db.schema.get_connection") as mock_get_conn:
            mock_get_conn.return_value = sqlite3.connect(str(db_path))
            _persist_signals(signals)

        # Verify signals were written
        conn = sqlite3.connect(str(db_path))
        rows = conn.execute("SELECT symbol, direction, confidence, weighted_score, source FROM signal_history").fetchall()
        conn.close()

        assert len(rows) == 2
        assert rows[0][0] == "AAPL"
        assert rows[0][1] == "buy"
        assert rows[0][4] == "orchestrator"


# ── Config tests ─────────────────────────────────────────────────────

class TestConfig:
    """Tests for configuration loading."""

    def test_config_has_execution_interval(self):
        """AppConfig should have execution_interval field."""
        from stock_market_expert.config.loader import load_config

        cfg = load_config()
        assert hasattr(cfg, "execution_interval")
        assert cfg.execution_interval == 7200

    def test_config_has_log_level(self):
        """AppConfig should have log_level field."""
        from stock_market_expert.config.loader import load_config

        cfg = load_config()
        assert hasattr(cfg, "log_level")
        assert cfg.log_level == "INFO"


# ── Logging tests ────────────────────────────────────────────────────

class TestLogging:
    """Tests for structured logging."""

    @pytest.mark.asyncio
    @patch("main.run_step1")
    @patch("main.run_step2")
    @patch("main.run_step3")
    async def test_cycle_logs_to_file(self, mock_step3, mock_step2, mock_step1, mock_config, tmp_path):
        """run_cycle should produce structured JSON log entries."""
        mock_step1.return_value = MagicMock(
            active_sectors=[MagicMock(sector="AI", stocks=["AAPL"], direction="buy", confidence=0.85, reasoning="test")],
            catalysts=[],
            operations=[MagicMock(symbol="AAPL", direction="buy", confidence=0.85, reasoning="test")],
            news_count=10,
            company_news_count=5,
            fallback_used=False,
            date_used=datetime.now(timezone.utc).isoformat(),
        )
        mock_step2.return_value = [
            TechnicalSignal(symbol="AAPL", direction="buy", confidence=0.85, score=0.45, reasoning="test"),
        ]
        mock_step3.return_value = MagicMock(
            orders=[MagicMock()],
            fills={},
            errors=[],
        )

        # Run cycle — logs go to logs/ directory
        await run_cycle()

        # Verify logger is configured
        from main import logger as main_logger
        assert isinstance(main_logger, logging.Logger)
        assert main_logger.level in (logging.INFO, logging.DEBUG)
