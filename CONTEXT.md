# Stock Market Expert — Domain Model

A CLI-based stock analysis and paper trading system that executes in sequential steps: news analysis → technical signal generation → order execution.

## News & Sector Analysis

**News Category**:
Alpha Vantage pre-defined classification (e.g., `technology`) used as the broad filter for initial news retrieval.
_Avoid_: custom tag, sector label

**Active Sector**:
A technology sub-sector identified as having unusual news activity, determined by the AI agent evaluating news volume, sentiment, and catalysts.
_Avoid_: trending sector, hot sector

**Catalyst**:
A specific event that could materially move a stock price — product launch, regulatory approval, merger, earnings report, or patent filing.
_Avoid_: trigger, event

**Operation**:
The action recommended by the AI agent based on news analysis: `buy`, `sell`, or `short`. Options are excluded from Step 1.
_Avoid_: trade, recommendation, signal

## Technical Analysis

**Technical Indicator**:
A computed metric used in the analysis pipeline: MACD (trend), ROC (momentum), or Volume (confirmation). Each returns a directional value and confidence.
_Avoid_: metric, factor

**Signal**:
A buy/sell/short recommendation produced by Step 2 from weighted aggregation of technical indicators. Contains direction, confidence score, and reasoning.
_Avoid_: recommendation, order, trade

**Confidence Score**:
The AI agent's certainty in a signal or sector assessment, expressed as a float between 0.0 and 1.0. Step 1 confidence and Step 2 confidence are independent — Step 2 does not reference Step 1 confidence.
_Avoid_: certainty, probability, weight

**Weighted Aggregation**:
The deterministic method of combining technical indicator outputs into a single score: `score = MACD × 0.5 + Volume × 0.3 + ROC × 0.2`.
_Avoid_: voting, consensus, ensemble

**Scope Narrowing**:
Step 1's sole purpose is to reduce the universe of stocks to a manageable set for Step 2. It does not influence Step 2's scoring.
_Avoid_: filtering, pre-screening, bias

## Execution

**Portfolio Balance**:
The current available cash in the IBKR paper account. Updated dynamically after each sell and before each buy.
_Avoid_: cash balance, account balance, available funds

**Execution Order**:
The rule that all sell operations must complete before any buy operations begin, ensuring accurate portfolio balance for position sizing.
_Avoid_: trading sequence, execution flow

**Position Sizing**:
The method of allocating buy capital across selected stocks proportional to each stock's confidence score.
_Avoid_: allocation, position amount, buy quantity

**Order**:
The IBKR paper account execution of a buy or sell operation. Contains symbol, quantity, price, and status.
_Avoid_: trade, transaction, fill

**Signal History**:
The persistent record of past signals per stock, stored in SQLite, used for deduplication and audit.
_Avoid_: log, history, cache

## System

**Execution Cycle**:
One complete run of Step 1 (news analysis) → Step 2 (signal generation) → Step 3 (order execution).
_Avoid_: run, iteration, loop

**Execution Interval**:
The fixed time between consecutive execution cycles: 2 hours (7200 seconds).
_Avoid_: frequency, period, schedule

**Structural Log**:
A structured JSON-formatted log entry capturing timestamp, level, step, action, and details for observability.
_Avoid_: plain log, text log, debug output
