# Execution Order: Sells Before Buys

All sell operations complete before any buy operations begin. Portfolio balance is updated after each sell, and buy position sizing uses the updated balance.

Selling first ensures accurate cash availability for position sizing. Parallel execution would require optimistic balance tracking with rollback on failure — significantly more complex and error-prone.

Considered Options: Sells-first, parallel execution, buys-first.
Consequences: If a sell fails, subsequent buys may have incorrect sizing. The system must handle partial execution gracefully (some sells succeed, some fail).
