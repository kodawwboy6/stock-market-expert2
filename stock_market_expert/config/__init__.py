"""Configuration loading module for the stock market expert system.

Uses pydantic-settings to load and validate configuration from .env files.
"""

from stock_market_expert.config.loader import AppConfig

__all__ = ["AppConfig"]
