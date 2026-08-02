# Software Development Guidelines

## Repository Guidelines

### Merge Strategy

When merging pull requests, always prefer **rebase** over merge commits. Use `git rebase` to integrate changes from the target branch into the PR branch, then fast-forward merge to main. Avoid creating merge commits (`git merge --no-ff`) unless explicitly requested.

## Accuracy Requirements

For any information that must be exact — external API calls, response schemas, endpoint URLs, request parameters, rate limits, or protocol details — **`/research` and `/domain-modeling` are required**.

- **Never infer** API response keys, parameter names, or endpoint paths from code alone.
- **Always verify** against the official documentation or a live API call before writing code, tests, or documentation.
- If the official docs are unclear, **query the live API** with a real key to get the actual response.
- When documenting an API in an ADR, cite the official docs URL and note which response keys were verified live.

This rule exists to prevent the kind of bugs where code assumes a response field that doesn't exist — e.g., reading `body` when the API returns `summary`, or reading `bid`/`ask` when `/price` only returns `price`.

## Coding Standards

### Issue tracker

Issues tracked as GitHub issues via `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Five canonical labels: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `CONTEXT.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.

### Config Handling

`load_config()` always returns an `AppConfig` instance — it never returns `None`.

- **Always call `load_config()` unconditionally.** Never guard it behind a conditional check.
- **Never use hardcoded fallback literals** (e.g. `"technology"`, `"localhost"`, `7497`) when a config default already exists in `AppConfig`. Use the config value directly via `cfg.attr_name`.
- **Never use `getattr(_config, "field", "default")`** as a fallback pattern. If a field has a default in `AppConfig`, just access it directly: `cfg.field_name`.
- Constructor parameters that accept optional kwargs to override config values are fine — use `or cfg.field_name` to apply the override or fall back to config.

#### Bad

```python
_config = None
if api_key is None:
    _config = load_config()

self.api_key = api_key or (_config.alpha_vantage_api_key if _config else "technology")
self.host = host or getattr(_config, "ibkr_insync_host", "localhost")
```

#### Good

```python
cfg = load_config()

self.api_key = api_key or cfg.alpha_vantage_api_key
self.host = host or cfg.ibkr_insync_host
```

### Constant Defaults

When a function or method needs a constant default value — especially as a default parameter — do **not** hardcode it. Instead:

1. Check if a relevant config already exists in `AppConfig` that covers this value.
2. If no suitable config exists, **add a new field to `AppConfig`** with the default, then use it.

This ensures all tunable values flow through a single source of truth (`AppConfig`) and can be overridden via `.env` without code changes.

#### Bad

```python
def run_pipeline(category: str = "technology"):
    ...

def analyze(sector: str = "AI", window: int = 20):
    ...
```

#### Good

```python
# In AppConfig:
news_category: str = "technology"
analysis_window: int = 20

def run_pipeline(category: Optional[str] = None):
    cfg = load_config()
    cat = category or cfg.news_category
    ...
```

### Function Naming

Function names must describe **what the function does**, not **how many steps** it performs. Avoid numbered or sequential names like `run_step1`, `run_step2`, `process_data_3`, etc.

- **Use descriptive names** that convey the specific action or purpose: `fetch_stock_quotes`, `validate_portfolio`, `calculate_moving_average`.
- **If a function calls multiple sub-steps internally**, name it after the overall goal: `analyze_market_trend` (not `run_step1`).
- **If you need multiple distinct steps**, extract them into separate functions with meaningful names and call them from a single orchestrator.

#### Bad

```python
def run_step1():
    ...

def run_step2():
    ...

def fetch_data_3():
    ...
```

#### Good

```python
def fetch_stock_quotes():
    ...

def validate_portfolio():
    ...

def calculate_moving_average():
    ...
```
