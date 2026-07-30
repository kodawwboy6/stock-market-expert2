# Development diary

This is to record the efford of human in the loop for developing this project. This may help development pure machine loop in the future.

Record would be marked per "loop", instead of day.

## Loops

### Loop 0 - setup

```sh
npx skills@latest add mattpocock/skills
```

Prompt:
```
/grill-with-docs <project description>
/setup-matt-pocock-skills
/ask-matt ...what should i do next?
/to-spec create a spec for this project...
/to-tickets ...
```

I then setup git repo in github as suggested by matt. It then generate script to setup tickets on github.

### Loop 1

Prompt:
```
/implement the github ticket #2
/code-review <- i believe it is codex skill, but it also works
```

Agent:
```
...
P1: fallback_used is never set to True
File: stock_market_expert/core/pipeline.py:142
In NewsPipeline.run(), fallback_used is always False:
...
P3: NewsPipeline.__init__ calls load_config() unconditionally
File: stock_market_expert/core/pipeline.py:68
...
Summary: The core design is solid. The most impactful fix is #1 (tracking fallback_used correctly) and #3 (avoiding unconditional load_config()). The rest are lower-priority improvements.
```

Prompt:
```
issue these 2 as github tickets
```

Agent:
```
Done — two GitHub issues created:
#8 — fallback_used always False — never tracks when fallback is actually used
#9 — load_config() called unconditionally even when all keys are passed
Issue #8 had a malformed body due to shell escaping, so I'd recommend editing it. Want me to push a fix to the body?
```

Prompt
```
/implement github ticket #8 and #9
```

Agent works and claims done

Prompt:
```
/code-review review the changes for this branch comparing to main
```

Agent:

Summary
| Axis | Findings | Worst issue |
|---|---|---|
| **Standards** | 7 findings | **Duplicated Code** — `fetch_news_with_retry` and `fetch_company_news_with_retry` share ~90% identical logic and should be extracted |
| **Spec** | 2 findings | **Sub-sectors missing** — spec asks for sub-sectors but `ActiveSector` has no field for them |

Prompt:
```
are these 2 issues optional? can i leave them alone now?
```

Agent:
```
Yes, both are safe to leave for now.
...
```

So I decide to end this loop here, but I forgot I've already implement #3 and so I run this again:


prompt:
```
/implement github ticket #3
```

agent:
```
(Try the check test cases first)
...
All 104 tests pass. I found 2 lint issues in the ticket #3 scope. Let me fix them.
...
All 36 tests pass. Let me now run the full test suite once more, then do a code review and commit.
...
Ticket #3 is already implemented
```

The then found out i'm working on wrongly created branch and so I discarded them all

### Loop 2

promp:
```
/Implement github ticket #4
```

Agent:
```
The Signal Engine (ticket #4) is already fully implemented on this branch...
```

I don't why it is already implemented. lets move on :/

### Loop 3

prompt:
```
/implement github ticket #5
```

agent:
```
...
All 144 tests pass (40 new execution tests + 104 existing). Typechecking passes. Committed to feature/04-execution-layer.
...
```

prompt:
```
/code-review changes of this branch vs main
```

agent reply with some minor issue and a weird logic found:
```python
equity = self._cash + sum(
    self._positions.get(s, 0.0) * 0.0 for s in self._positions
)
```
```
The get_equity call in calculate_quantity passes 0.0 for all prices, making the position contribution zero. This means position sizing for buys ignores current holdings. It's a logic bug, not a smell per se.
```

I've modified the code myself for usage of equity and prompt:
```
find all equity calculation (in portfolio_tracker and order_builder) and correct them to use get_equity in portfolio_tracker
```

Agent create another get_equity in OrderBuilder. I realize OrderBuilder and PortfolioTracker has its own positions. so I prompt:
```
/grill-with-docs I don't think it is a good fix. OrderBuilder and PortfolioTracker has its own positions, which is not a good design. I think PortfolioTracker should hold the only source of truth about positions, as it is part of portfolio, and OrderBuilder should get equity from PortfolioTracker. update docs and make a plan to fix this
```

Q: is it domain decision, or layering decision
A: domain

Q: OrderBuilder hold a reference to a PortfolioTracker, or build_orders() receives the portfolio state snapshot and passes it through
A: hold reference

Q: What about the set_portfolio() / set_cash() / apply_order() methods on OrderBuilder
A: apply_order should be implemented in ExecutionOrder, with PortfolioTracker as input param. it can be applied without OrderBuilder. By the way i guess it is a good idea to mark if the order is applied and prevent redundant operation

Q: Idempotency — how should we prevent redundant application
A: Option A: Add applied: bool = False to ExecutionOrder

plan is settled and it applied the fix. i start a new session and do code review again

agent found that api call has no retry upon failure

prompt:
```
/grill-me all operation involve external api should have a retry logic, with a time limit that expire before next loop of run. write a helper function and apply it to them
```

agent created async_retry_with_backoff

### Loop 4

prompt to implement #6

agent have it done and marked ticket as closed. i'm sure how it can do that.
it then run review but nth was found

i've opened a new session and run review again:

Standards
No explicit CODING_STANDARDS.md or CONTRIBUTING.md found. Review uses the smell baseline + existing codebase conventions (dataclasses, explicit types, docstring Args format,

### manual verify

I've checked the env file and found ORDER_TYPE was not being used. /diagnosing-bugs is used to fix this.

after it is solved, i ask agent to check every env var. many of them are dead:

12 out of 35 variables are dead — they exist in the config but are never actually wired through to any code path. They fall into 3 categories:
IBKR REST API keys/URL (IBKR_TRADING_CLIENT_ID, IBKR_TRADING_CLIENT_SECRET, IBKR_BASE_URL) — The project uses IBKR's insync (TWS/Gateway) protocol, not their REST API. These are irrelevant.
Technical analysis params (RSI_PERIOD, BOLLINGER_PERIOD, BOLLINGER_STD) — SignalEngine only supports MACD/ROC/Volume. No RSI or Bollinger implementation exists.
Risk/scheduling flags (MAX_POSITION_PCT, MAX_DAILY_TRADES, MAX_PORTFOLIO_RISK_PCT, AUTO_EXECUTE, SCHEDULE_CRON, LOG_RETENTION_DAYS) — Either dead code or hardcoded defaults that bypass the config entirely.

prompt:
```
/gill-me create 3 tickets w.r.t. these 3 categories
```

agent didn't ask me any question and create 3 tickets. they are then all implemented

prompt:
```
/to-tickets check the project for any hardcoded settings. create a ticket to config them in env file
```

after ticket draft i've removed the the var about init capacity. then implement them.

an md file in .scratch is created. not sure what is it.

prompt: /code-review review since main

prompt:
```
/grill-me write a skill with `/writing-great-skill` called "merge-this". ask user which tickets to close if it isn't specified. ask if rebase or merge is preferred. push current branch to remote, create a new remote branch if needed, make a pull request that close those tickets in description. rebase or merge to main branch. switch current repo to main branch. fetch and pull the change.
```

```
/writing-great-skills update /merge-this such that, when switching branch to main and there are some local changes, stash all changes to _temp, switch the branch, do fetch and pull, pop that stash
```

TODO: try improve-codebase-architecture
