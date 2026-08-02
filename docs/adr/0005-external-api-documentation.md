# External API Documentation: Alpha Vantage, Finnhub, Twelve Data, Alpaca

Each external API is used by a dedicated provider module. This ADR records the official documentation URLs and the specific endpoints the project consumes, verified against live API responses.

---

## Alpha Vantage — News & Sentiment

- **Provider**: `stock_market_expert.data.alpha_vantage_news_provider`
- **Base URL**: `https://www.alphavantage.co/query`
- **Official Docs**: <https://www.alphavantage.co/documentation/#news-sentiment>
- **Endpoint used**: `NEWS_SENTIMENT`
- **Required params**: `function=NEWS_SENTIMENT`, `apikey`
- **Optional params**:
  - `categories` — filter by topic (e.g., `technology`). Supported topics: `blockchain`, `earnings`, `ipo`, `mergers_and_acquisitions`, `financial_markets`, `economy_fiscal`, `economy_monetary`, `economy_macro`, `energy_transportation`, `finance`, `life_sciences`, `manufacturing`, `real_estate`, `retail_wholesale`, `technology`.
  - `tickers` — filter by stock/crypto/forex symbols (e.g., `AAPL,CRYPTO:BTC`)
  - `topics` — filter by news topics (same list as above, comma-separated)
  - `time_from` / `time_to` — `YYYYMMDDTHHMM` format (e.g., `20220410T0130`)
  - `sort` — `LATEST` (default), `EARLIEST`, or `RELEVANCE`
  - `limit` — 50 (default) to 1000
- **Top-level response keys**:
  - `items` — number of items returned
  - `sentiment_score_definition` — description of sentiment scoring
  - `relevance_score_definition` — description of relevance scoring
  - `feed` — array of news article objects
- **Each `feed[]` object** (verified live):
  - `title` — string
  - `url` — string
  - `time_published` — `YYYYMMDDTHHMM` format (e.g., `20260802T073249`)
  - `authors` — array of strings
  - `summary` — string (not `body`)
  - `banner_image` — string URL or `null`
  - `source` — string
  - `category_within_source` — string
  - `source_domain` — string
  - `topics` — array of `{topic, relevance_score}` objects
  - `overall_sentiment_score` — float (e.g., `0.007915`)
  - `overall_sentiment_label` — one of: `Neutral`, `Somewhat-Bearish`, `Somewhat-Bullish`, `Bullish`, `Bearish`
  - `ticker_sentiment` — array of `{ticker, relevance_score, ticker_sentiment_score, ticker_sentiment_label}` objects
- **Sentiment scale** (from `sentiment_score_definition`):
  - `x <= -0.35`: Bearish
  - `-0.35 < x <= -0.15`: Somewhat-Bearish
  - `-0.15 < x < 0.15`: Neutral
  - `0.15 <= x < 0.35`: Somewhat-Bullish
  - `x >= 0.35`: Bullish
- **Rate limit**: 30 requests/day (free tier)
- **Config field**: `alpha_vantage_api_key`

> ⚠️ **Note**: The code uses `body` to access the article text, but the actual API returns `summary`. The `body` key does not exist in the response.

---

## Finnhub — Company News

- **Provider**: `stock_market_expert.data.finnhub_news_provider`
- **Base URL**: `https://finnhub.io/api/v1`
- **Official Docs**: <https://finnhub.io/docs/api/company-news>
- **Endpoint used**: `/company-news`
- **Required params**: `token`, `symbol`
- **Optional params**: `from` (YYYY-MM-DD), `to` (YYYY-MM-DD)
- **Response**: array of objects (verified live):
  - `category` — string (e.g., `company`)
  - `datetime` — Unix timestamp (e.g., `1785632580`)
  - `headline` — string
  - `id` — integer
  - `image` — string URL
  - `related` — string (ticker symbol, e.g., `AAPL`)
  - `source` — string
  - `summary` — string
  - `url` — string
- **Rate limit**: 60 requests/minute (free tier)
- **Config field**: `finnhub_api_key`

---

## Twelve Data — OHLCV & Real-time Quotes

- **Provider**: `stock_market_expert.data.twelve_data_provider`
- **Base URL**: `https://api.twelvedata.com`
- **Official Docs**:
  - Time series: <https://twelvedata.com/docs/api/historical-symbols>
  - Price quote: <https://twelvedata.com/docs/api/real-time-price>
- **Endpoints used**:

### `/time_series` — historical OHLCV data (verified live)
- **Params**: `symbol`, `interval`, `start_date`, `end_date`, `outputsize`, `format=JSON`, `apikey`
- **Response** (verified live):
  - `meta` — `{symbol, interval, currency, exchange_timezone, exchange, mic_code, type}`
  - `values` — array of:
    - `datetime` — string (YYYY-MM-DD)
    - `open` — string (e.g., `187.14999`)
    - `high` — string
    - `low` — string
    - `close` — string
    - `volume` — string (e.g., `82488700`)
  - `status` — `"ok"` or `"error"`
- **Error response**: `{code: 400, message: string, status: "error", meta: object}`
- **Rate limit**: Varies by plan; project uses exponential backoff retries
- **Config field**: `twelve_data_api_key`

### `/price` — real-time single-symbol quote (verified live)
- **Params**: `symbol`, `apikey`
- **Response** (verified live): `{price: string}` (e.g., `309.029999`)
- **Note**: The code assumes response keys `price`, `bid`, `ask`, `volume`, but the actual response only contains `price`.

---

## Alpaca — Market Data & Paper Trading

- **Provider**: `stock_market_expert.data.alpaca_provider`
- **Trading API base URL**: `https://paper-api.alpaca.markets` (paper) / `https://api.alpaca.markets` (live)
- **Market Data API base URL**: `https://data.alpaca.markets`
- **Official Docs**: <https://alpaca.markets/docs/api-documentation/api-overview/>
- **Auth**: `Apca-Api-Key-Id` + `Apca-Api-Secret-Key` headers

### `/v2/account` — portfolio balance (verified live)
- **Response** (verified live):
  - `cash` — string (e.g., `100000`)
  - `equity` — string (e.g., `100000`)
  - `buying_power` — string (e.g., `400000`)
  - `portfolio_value` — string
  - `status` — string (e.g., `ACTIVE`)
  - `currency` — string
  - `shorting_enabled` — boolean
  - `multiplier` — string

### `/v2/positions` — open positions (verified live)
- **Response**: array (empty `[]` if no positions)
- **Each position** (documented, not verified live — paper account has no positions):
  - `symbol` — string
  - `qty` — string
  - `avg_entry_price` — string
  - `market_value` — string
  - `unrealized_pl` — string

### `/v2/stocks/{symbol}/trades` — historical trade data
- **Base URL**: `https://data.alpaca.markets` (market data API, **not** trading API)
- **Params**: `start`, `end`, `limit`
- **Response** (verified live): `{next_page_token, symbol, trades}`
- **Note**: The code uses `paper-api.alpaca.markets` as the base URL for `/stocks/{symbol}/trades`, but this endpoint returns `404 Not Found` on the trading API. Market data endpoints require `data.alpaca.markets`.

### Auth headers (verified)
- `Apca-Api-Key-Id` — Alpaca API key
- `Apca-Api-Secret-Key` — Alpaca secret key

---

## Considered Options

- Single API (Alpha Vantage only) — insufficient for deep-dive per-stock analysis.
- Single API (Finnhub only) — lacks sentiment scores and category-level filtering.
- Hybrid (current): Alpha Vantage for broad category news → Finnhub for per-stock deep dive → Twelve Data for technical indicators → Alpaca for execution.

## Consequences

- More infrastructure to manage (4 API keys, 4 rate limits, 4 error modes).
- Eliminated single-point-of-failure risk.
- Each provider has retry-with-backoff and date-fallback built in.

## Known Issues

- **Alpha Vantage**: Code reads `body` from response but the API returns `summary`.
- **Twelve Data price endpoint**: Code reads `bid`, `ask`, `volume` from `/price` but the API only returns `price`.
- **Alpaca market data**: Code uses `paper-api.alpaca.markets` base URL for `/stocks/{symbol}/trades` but the endpoint lives on `data.alpaca.markets`.
