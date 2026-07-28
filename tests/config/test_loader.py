"""Tests for the config loader module."""

import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from stock_market_expert.config.loader import AppConfig, load_config


class TestAppConfig:
    """Tests for the AppConfig model."""

    def test_default_values(self, tmp_path):
        """Config should have sensible defaults when no .env is present."""
        # Use an empty .env file
        env_file = tmp_path / ".env"
        env_file.write_text("")

        config = AppConfig(_env_file=env_file)

        assert config.news_category == "technology"
        assert config.news_max_items == 50
        assert config.macd_fast == 12
        assert config.macd_slow == 26
        assert config.macd_signal == 9
        assert config.rsi_period == 14
        assert config.max_position_pct == 0.10
        assert config.min_signal_confidence == 0.7
        assert config.max_daily_trades == 10
        assert config.order_type == "market"
        assert config.run_mode == "continuous"
        assert config.paper_account is True
        assert config.lm_studio_base_url == "http://localhost:1234/v1"

    def test_loads_from_env(self, tmp_path):
        """Config should load values from a .env file."""
        env_file = tmp_path / ".env"
        env_file.write_text(
            "NEWS_CATEGORY=biotech\n"
            "MACD_FAST=10\n"
            "MACD_SLOW=20\n"
            "MAX_POSITION_PCT=0.20\n"
            "LM_STUDIO_BASE_URL=http://custom:8080/v1\n"
        )

        config = AppConfig(_env_file=env_file)

        assert config.news_category == "biotech"
        assert config.macd_fast == 10
        assert config.macd_slow == 20
        assert config.max_position_pct == 0.20
        assert config.lm_studio_base_url == "http://custom:8080/v1"

    def test_validate_required_fields_empty(self, tmp_path):
        """Missing API keys should be reported."""
        env_file = tmp_path / ".env"
        env_file.write_text("")

        config = AppConfig(_env_file=env_file)
        missing = config.validate_required_fields()
        assert "ALPHA_VANTAGE_API_KEY" in missing
        assert "FINNHUB_API_KEY" in missing

    def test_validate_required_fields_partial(self, tmp_path):
        """Partial API keys should report only missing ones."""
        env_file = tmp_path / ".env"
        env_file.write_text(
            "ALPHA_VANTAGE_API_KEY=abc123\n"
            "FINNHUB_API_KEY=def456\n"
            "TWELVE_DATA_API_KEY=ghi789\n"
            "ALPACA_API_KEY=jkl012\n"
            "ALPACA_SECRET_KEY=mno345\n"
        )

        config = AppConfig(_env_file=env_file)
        missing = config.validate_required_fields()
        assert missing == []

    def test_validate_required_fields_missing_alpaca_secret(self, tmp_path):
        """Missing ALPACA_SECRET_KEY should be reported."""
        env_file = tmp_path / ".env"
        env_file.write_text("ALPACA_API_KEY=abc123\n")

        config = AppConfig(_env_file=env_file)
        missing = config.validate_required_fields()
        assert "ALPACA_API_KEY / ALPACA_SECRET_KEY" in missing


class TestLoadConfig:
    """Tests for the load_config function."""

    def test_returns_app_config(self):
        """load_config should return an AppConfig instance."""
        config = load_config()
        assert isinstance(config, AppConfig)
