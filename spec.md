# Stock Market Expert MVP — Build Spec

## Problem Statement

A CLI-based stock analysis and paper trading system that executes in sequential steps: news analysis → technical signal generation → order execution. The user wants to identify active technology sectors from news, generate buy/sell/short signals using technical analysis, and execute trades to an IBKR paper account — all without a web interface.

## Solution

A Python application that runs in a continuous loop (every 2 hours), sequentially executing:

1. **Step 1 — News Analysis**: Fetch technology news via Alpha Vantage (broad filter) → Finnhub (deep dive on identified stocks) → AI agent (LM Studio) extracts active sectors and operation recommendations (buy/sell/short).
2. **Step 2 — Signal Generation**: For stocks from Step 1, compute MACD, ROC, and Volume indicators from Twelve Data (historical) and Alpaca (real-time) → deterministic weighted aggregation → independent confidence-scored signals.
3. **Step 3 — Execution**: All sells complete before buys begin → position sizing by confidence-weighted allocation → order execution via IBKR paper account via ib_insync.

## User Stories

1. As a stock analyst, I want the system to fetch technology news from Alpha Vantage and perform deep-dive analysis via Finnhub, so that I get a comprehensive view of active sectors.
2. As a stock analyst, I want the AI agent to extract active sectors and sub-sectors from news, so that I can focus trading on the most relevant areas.
3. As a stock analyst, I want the system to identify catalysts (product launches, regulatory approvals, mergers, earnings, patents) in the news, so that I can anticipate price movements.
4. As a stock analyst, I want the system to recommend buy/sell/short operations based on news analysis, so that I can act on information-driven opportunities.
5. As a stock analyst, I want the system to compute MACD, ROC, and Volume indicators for identified stocks, so that I can validate news-based recommendations with technical analysis.
6. As a stock analyst, I want the system to use deterministic weighted aggregation (MACD × 0.5 + Volume × 0.3 + ROC × 0.2) to combine technical indicators, so that signals are consistent and auditable.
7. As a stock analyst, I want the system to generate independent confidence scores for each signal, so that I can trust the technical analysis without news bias.
8. As a stock analyst, I want the system to filter out duplicate signals (same stock, same direction), so that I don't execute redundant trades.
9. As a stock analyst, I want all sell operations to complete before any buy operations begin, so that portfolio balance is accurate for position sizing.
10. As a stock analyst, I want buy capital allocated proportionally to each stock's confidence score, so that higher-conviction signals receive more capital.
11. As a stock analyst, I want the system to execute trades to an IBKR paper account, so that I can test the strategy without real money.
12. As a stock analyst, I want the system to run continuously every 2 hours, so that I get regular market analysis without manual intervention.
13. As a stock analyst, I want all configuration (API keys, thresholds, risk limits) in a `.env` file, so that I can change settings without modifying code.
14. As a stock analyst, I want structured JSON logs capturing timestamp, level, step, action, and details, so that I can observe and debug the system.
15. As a stock analyst, I want the system to persist signal history in SQLite, so that I can audit past signals and trades.
16. As a stock analyst, I want the system to handle API errors gracefully with retries, so that occasional failures don't break the entire pipeline.
17. As a stock analyst, I want the system to be managed by systemd, so that it auto-restarts on failure and survives reboots.

## Implementation Decisions

### Architecture
- Sequential execution pipeline: Step 1 → Step 2 → Step 3 per cycle
- Continuous loop with configurable interval (default 7200 seconds)
- systemd-managed process with auto-restart on failure

### Data Sources
- **Alpha Vantage** `/news` with `categories=technology` for broad news filtering (30 req/day)
- **Finnhub** `/company-news` for deep-dive on identified stocks (60 req/min)
- **Twelve Data** for historical OHLCV data (90-day window)
- **Alpaca** `/quotes` for real-time price data
- All API keys configured via `.env`

### AI Agent
- Local LM Studio via OpenAI-compatible API endpoint
- Configurable base URL and model name via `.env`
- No external API costs or rate limits
- Step 1: News analysis — extract active sectors, catalysts, operation recommendations
- Step 2: Technical analysis — compute indicators and generate signals

- All LLM HTTP calls use `timeout=7200.0` (2 hours) — local inference can take minutes
### Technical Analysis
- **ROC** (10-day) — momentum detection, weight 0.2
- **Volume** (relative to average) — confirmation, weight 0.3
- Deterministic weighted aggregation: `score = MACD × 0.5 + Volume × 0.3 + ROC × 0.2`
- Thresholds: >0.3 → buy, <-0.3 → sell/short, between →观望
- Step 1 and Step 2 confidence scores are independent — no cross-referencing

### Execution
- **ib_insync** library to connect to IBKR TWS/Gateway
- Sells-first execution order: all sells complete before buys begin
- Portfolio balance updated dynamically after each sell
- Position sizing: proportional to confidence score
- Market orders with day time-in-force
- Signal deduplication: skip if same stock has same direction signal

### Error Handling
- Step 1 (news): retry 3 times with exponential backoff; if still failing, use yesterday's data
- Step 2 (signals): retry indefinitely until success; skip cycle if still failing
- Step 3 (execution): retry indefinitely until success; skip cycle if still failing
- All errors logged to structured JSON log files
- Custom error handler module for centralized logging

### Persistence
- SQLite database for signal history and trade history
- Signal history used for deduplication and audit trail
- Configurable log retention period via `.env`

### Configuration
- All settings in `.env`:
  - API keys (Alpha Vantage, Finnhub, Twelve Data, Alpaca)
  - LM Studio base URL and model name
  - News category, confidence thresholds
  - Technical analysis parameters (MACD, ROC, Volume settings)
  - Risk limits (max position %, min confidence, max daily trades)
  - IBKR connection settings (host, port, account ID)
  - Execution interval, run mode, log level
  - Retry delay factor and max delay

### Monitoring
- systemd service with auto-restart on failure
- Structured JSON logs for observability
- Signal and trade history in SQLite for audit

## Testing Decisions

- Test external behavior only (API responses, signal outputs, order submissions)
- Module-level tests for:
  - Weighted aggregation logic (deterministic, no mocks needed)
  - Signal deduplication logic
  - Error handling and retry behavior
- Integration tests for:
  - API client error handling (mocked responses)
  - IBKR order submission (test with paper account)
- No mock data — all data sources use real APIs

## Out of Scope

- Options trading (Call/Put, strike price, expiry) — reserved for a future phase
- Real account trading — paper account only for this MVP
- Web interface or dashboard
- Mobile notifications or alerts
- Backtesting framework
- Multi-language support (English UI/logs only)
- Performance optimization for large stock universes (target: ~20 stocks per cycle)
- Custom indicator development (only MACD, ROC, Volume)

## Further Notes

- The system is designed as a CLI tool — no GUI considerations
- LM Studio runs locally, eliminating API costs and rate limits
- The systemd setup script should be included in the deliverables
- All ADRs are recorded in `docs/adr/` and should be respected during implementation
- The domain model in `CONTEXT.md` defines the ubiquitous language — all code and tests should use these terms
