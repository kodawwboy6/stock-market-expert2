# ADR 0006: LLM Service Timeout

## Status

Accepted

## Context

The project uses a local LM Studio instance as an LLM inference service, called via HTTP on `http://localhost:1234/v1/chat/completions`. Large language models on local hardware can take minutes to generate responses — far longer than the 5-second default httpx timeout, which caused `timed out` errors during news analysis.

## Decision

Every LLM service call must use an explicit timeout of **2 hours (7200 seconds)**.

This applies to all `httpx.post()` calls that target the LM Studio API endpoint, regardless of which module makes the call.

The timeout is set as a keyword argument on each `httpx.post()` call:

```python
response = httpx.post(
    f"{self.base_url}/chat/completions",
    json={...},
    timeout=7200.0,
)
```

## Rationale

- Local LLM inference is inherently slow — 2 hours is a generous upper bound for any single generation.
- The default httpx timeout is 5 seconds, which is orders of magnitude too short.
- A 2-hour timeout is consistent with the project's **Execution Interval** of 2 hours — a single analysis cycle should not be killed by an artificial timeout.
- External API calls (Alpha Vantage, Finnhub, etc.) use shorter timeouts (15–30 seconds) because they are fast network services; LLM inference is a fundamentally different workload.

## Consequences

- LLM calls will not be silently killed by a 5-second default timeout.
- A genuinely hung LLM will still be reclaimed after 2 hours.
- All future LLM calls must include `timeout=7200.0` explicitly — no reliance on defaults.
