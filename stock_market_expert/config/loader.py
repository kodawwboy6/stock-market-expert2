"""Configuration loader using pydantic-settings.

Loads all application settings from .env files with type validation
and sensible defaults.
"""


from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseSettings):
    """Application configuration loaded from .env files.

    All settings are validated on load. Missing required fields
    will raise a ValidationError.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # === API Keys ===
    alpha_vantage_api_key: str = ""
    finnhub_api_key: str = ""
    twelve_data_api_key: str = ""
    alpaca_api_key: str = ""
    alpaca_secret_key: str = ""
    alpaca_base_url: str = "https://paper-api.alpaca.markets"

    # === IBKR ===
    ibkr_account_id: str = ""
    ibkr_insync_host: str = "localhost"
    ibkr_insync_port: int = 7497

    # === AI Agent (LM Studio) ===
    lm_studio_base_url: str = "http://localhost:1234/v1"
    lm_studio_model: str = "lms-7b"

    # === News Analysis ===
    news_category: str = "technology"
    news_max_items: int = 50
    news_confidence_threshold: float = 0.6

    # === Technical Analysis ===
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    history_days: int = 90

    # === Risk Management ===
    min_signal_confidence: float = 0.7

    # === Execution ===
    order_type: str = "MKT"
    paper_account: bool = True

    # === Scheduling ===
    run_mode: str = "continuous"
    execution_interval: int = 7200

    # === Logging ===
    log_level: str = "INFO"

    def validate_required_fields(self) -> list[str]:
        """Return a list of missing required API keys.

        Returns:
            List of missing key names. Empty if all present.
        """
        missing = []
        if not self.alpha_vantage_api_key:
            missing.append("ALPHA_VANTAGE_API_KEY")
        if not self.finnhub_api_key:
            missing.append("FINNHUB_API_KEY")
        if not self.twelve_data_api_key:
            missing.append("TWELVE_DATA_API_KEY")
        if not self.alpaca_api_key or not self.alpaca_secret_key:
            missing.append("ALPACA_API_KEY / ALPACA_SECRET_KEY")
        return missing


def load_config() -> AppConfig:
    """Load application configuration from .env.

    Returns:
        AppConfig instance with validated settings.
    """
    return AppConfig()
