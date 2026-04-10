from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )

    # ── LLM ───────────────────────────────────────────────────────────────────
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # ── Alpaca ────────────────────────────────────────────────────────────────
    alpaca_api_key: str = ""
    alpaca_secret_key: str = ""
    alpaca_base_url: str = "https://paper-api.alpaca.markets"

    # ── Alpha Vantage ─────────────────────────────────────────────────────────
    alpha_vantage_api_key: str = ""

    # ── NewsAPI ───────────────────────────────────────────────────────────────
    news_api_key: str = ""

    # ── Redis ─────────────────────────────────────────────────────────────────
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str = ""

    # ── LangSmith (optional) ──────────────────────────────────────────────────
    langchain_tracing_v2: bool = False
    langchain_api_key: str = ""
    langchain_project: str = "invest-bot"
    langchain_endpoint: str = "https://api.smith.langchain.com"

    # ── Risk controls ─────────────────────────────────────────────────────────
    max_position_size_usd: float = 1000.0
    max_portfolio_risk_pct: float = 0.02
    stop_loss_pct: float = 0.05
    max_daily_trades: int = 10

    # ── Scheduling ────────────────────────────────────────────────────────────
    crew_run_interval_minutes: int = 60
    memory_reset_day: str = "sunday"
    memory_reset_hour: int = 2

    # ── Scraping ──────────────────────────────────────────────────────────────
    capitol_trades_url: str = "https://www.capitoltrades.com/trades"
    scrape_delay_seconds: int = 3
    playwright_headless: bool = True

    @property
    def is_paper_trading(self) -> bool:
        return "paper-api" in self.alpaca_base_url


settings = Settings()
