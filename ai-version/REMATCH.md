# One AI Rematch

## Critique of the first AI version

After comparing the minimal AI implementation with the production version, the
largest missing pieces are:

1. retry policy is absent
2. provider failures and schema failures are not separated
3. no observability exists for token usage or latency

## One-rematch recommendation

Keep the small structure, but add only these three capabilities:

- a provider adapter interface
- explicit error types for transport vs invalid output
- one structured log record per provider call

Do not copy every production extra into the AI version.

Reason:
the rematch should improve the independent design rather than recreate the
existing solution line-for-line.

## Result

The rematch confirms that the production implementation is more robust, while
the AI version remains a useful minimal reference implementation.
