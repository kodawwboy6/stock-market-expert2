# Signal Aggregation: Deterministic Weighted Scoring

Combine technical indicator outputs into a single score using fixed weights: `score = MACD × 0.5 + Volume × 0.3 + ROC × 0.2`. Thresholds: >0.3 → buy, <-0.3 → sell/short, between →观望.

Deterministic scoring avoids the non-determinism and cost of LLM-based aggregation while providing consistent, auditable signal generation. Simple majority voting ignores indicator reliability differences.

Considered Options: Deterministic weighted scoring, LLM-based aggregation, simple majority voting.
Consequences: Future skill additions require re-evaluating weights. The fixed thresholds mean signals are reproducible across runs given identical input data.
