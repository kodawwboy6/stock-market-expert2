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

So I decide to end this loop here

### Loop 2

prompt
```
/implement github ticket #3
```
