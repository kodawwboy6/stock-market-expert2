# Hybrid News Sourcing: Alpha Vantage → Finnhub

Use Alpha Vantage `/news` with `categories=technology` for broad initial filtering, then Finnhub `/company-news` for deep-dive on identified stocks.

Alpha Vantage provides category-level filtering at 30 requests/day — sufficient for a single broad pass. Finnhub at 60 requests/minute handles per-stock deep dives without throttling risk. A single-source approach would either lack breadth (Finnhub only) or depth (Alpha Vantage only).

Considered Options: Alpha Vantage only, Finnhub only, hybrid.
Consequences: Adds complexity in the data pipeline but eliminates throttling risk and improves sector precision.
