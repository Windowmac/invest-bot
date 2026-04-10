# invest-bot

Autonomous multi-agent investment research and paper trading system.

## Architecture

Five CrewAI agents run in a sequential pipeline, communicating results via task context and persisting signals in Redis:

| Agent | Role | Data Sources |
|---|---|---|
| Stock Research | Technical + fundamental analysis | Alpha Vantage (free tier, 25 req/day) → yfinance fallback |
| News Aggregator | Market sentiment from headlines | NewsAPI + VADER sentiment |
| Congress Tracker | STOCK Act disclosure patterns | Capitol Trades (Playwright scraper) |
| Signal Aggregator | Multi-source confirmation filter | Synthesizes above 3 agents |
| Trading Executor | Order placement + risk management | Alpaca (paper trading) |

```
Redis ←── signals / pipeline events
  ↑
  └── crew container (all 5 agents)
        ├── tools/alpha_vantage_tool.py   (AV + yfinance)
        ├── tools/news_tool.py             (NewsAPI + VADER)
        ├── tools/scraper_tool.py          (Playwright → Capitol Trades)
        └── tools/alpaca_tool.py           (bracket orders)
```

## Quick Start

### 1. Configure environment

```bash
cp .env.example .env
# Edit .env — fill in all API keys before running
```

Required keys:
- `OPENAI_API_KEY` — for agent LLM calls
- `ALPACA_API_KEY` + `ALPACA_SECRET_KEY` — Alpaca paper account
- `ALPHA_VANTAGE_API_KEY` — free at alphavantage.co (25 req/day)
- `NEWS_API_KEY` — free at newsapi.org (100 req/day)

### 2. Run with Docker

```bash
make build    # build images (first time, ~5 min for Playwright image)
make up       # start Redis + crew
make logs     # tail logs
make down     # stop everything
```

### 3. Run locally (without Docker)

```bash
make install                     # pip install + playwright install chromium
REDIS_HOST=localhost python scripts/run_crew.py
```

### 4. Manual memory reset

```bash
make reset    # archives Redis state → memory/archives/ then clears agent keys
```

## Project Structure

```
invest-bot/
├── agents/
│   ├── crew.py              # Main orchestration — builds and runs full pipeline
│   ├── stock_research.py    # Technical + fundamental analysis agent
│   ├── news_aggregator.py   # NewsAPI + VADER sentiment agent
│   ├── congress_tracker.py  # Capitol Trades scraping agent
│   ├── trading_executor.py  # Alpaca order placement agent
│   └── memory_reset.py      # Archive + flush Redis keys
├── tools/
│   ├── alpha_vantage_tool.py  # AV API calls with yfinance fallback
│   ├── news_tool.py           # NewsAPI + VADER
│   ├── scraper_tool.py        # Playwright scraper for Capitol Trades
│   └── alpaca_tool.py         # Bracket orders via alpaca-py
├── schemas/
│   ├── config.py             # Pydantic Settings (reads .env)
│   └── signals.py            # TradeSignal, NewsItem, CongressTrade models
├── memory/
│   ├── redis_store.py        # Pub/sub helpers, signal storage, reset utilities
│   └── archives/             # Weekly JSON snapshots (gitignored)
├── scripts/
│   ├── run_crew.py           # Entry point: runs pipeline on APScheduler interval
│   └── weekly_reset.py       # Standalone reset script
├── tests/                    # Unit tests with mocked API responses
├── docker/
│   ├── Dockerfile            # Python 3.11-slim (lightweight services)
│   └── Dockerfile.playwright # Playwright image (crew container needs Chromium)
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

## Risk Controls

All enforced by the Trading Executor agent and `settings`:

| Control | Default | Env var |
|---|---|---|
| Max position size | $1,000 | `MAX_POSITION_SIZE_USD` |
| Portfolio risk per trade | 2% | `MAX_PORTFOLIO_RISK_PCT` |
| Stop-loss (bracket order) | 5% | `STOP_LOSS_PCT` |
| Daily trade limit | 10 | `MAX_DAILY_TRADES` |
| Min signal confidence | 0.65 | hardcoded in trading task |
| Min sources confirming | 2 of 3 | hardcoded in aggregator task |

Stop-loss is implemented via Alpaca's native bracket orders — it is **not** polled from Python and survives container restarts.

## Data Source Notes

**Alpha Vantage (free tier):** 25 requests/day. A 15-second delay is enforced between calls. yfinance is the automatic fallback for price and indicator data when the limit is hit. Fundamentals (`OVERVIEW` endpoint) will return an error when the daily quota is exhausted — yfinance fallback covers most fields.

**NewsAPI (free tier):** 100 requests/day. Some sources have a 24-hour article delay on the free tier, but the top headlines endpoint is real-time. Breaking news signals may lag for smaller sources.

**Capitol Trades scraper:** No public API exists. Playwright scrapes the public trades table. Known risks:
- Cloudflare bot protection can block headless browsers silently
- HTML structure changes will break selectors in `tools/scraper_tool.py` `_parse_trades()`
- The site's `robots.txt` disallows crawlers — review ToS for your use case
- If scraping becomes unreliable, Quiver Quant (~$20/mo) offers a congressional trading API

## Testing

```bash
make install          # install dev deps
pytest tests/ -v      # run all tests

# Individual agent tests
pytest tests/test_congress_tracker.py -v   # also tests HTML parsing against fixture
```

Tests mock all external API calls. The congress tracker test parses against `tests/fixtures/capitol_trades_page.html` — update this fixture if the site's HTML structure changes and you update the selectors.

## Legal Disclaimer

This system is for **educational and paper trading purposes only**. Nothing here constitutes financial advice.

- Congressional trading data analyzed here comes from public STOCK Act disclosures — analyzing it is legal
- Automated trading has significant risk of financial loss — validate thoroughly in paper mode before considering live trading
- Consult SEC resources on automated trading rules, including pattern day trading limits (PDT rule)
- Consult a licensed financial advisor before committing real capital
