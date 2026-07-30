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

    # === Signal Engine ===
    roc_period: int = 10
    volume_lookback: int = 20
    buy_threshold: float = 0.3
    sell_threshold: float = -0.3

    # === Aggregation Weights ===
    weight_macd: float = 0.5
    weight_volume: float = 0.3
    weight_roc: float = 0.2

    # === Confidence Scaling ===
    macd_confidence_multiplier: float = 10.0
    roc_confidence_scale: float = 20.0
    volume_confidence_high_scale: float = 3.0
    volume_confidence_low_scale: float = 2.0

    # === Risk Management ===
    min_signal_confidence: float = 0.7

    # === Execution ===
    order_type: str = "MKT"
    paper_account: bool = True

    # === Execution Deadlines ===
    signal_deadline: int = 300
    execution_deadline: int = 300

    # === Retry & Backoff ===
    retry_max_retries: int = 5
    retry_delay_factor: float = 1.0
    retry_max_delay: float = 30.0
    ibkr_retry_max_retries: int = 3
    ibkr_retry_delay_factor: float = 1.0
    ibkr_retry_max_delay: float = 30.0
    ibkr_order_retry_max_retries: int = 1

    # === Infrastructure ===
    db_path: str = "data/stock_market_expert.db"
    log_dir: str = "logs"
    ibkr_api_timeout: int = 10

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
