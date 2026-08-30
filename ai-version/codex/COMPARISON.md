# Real AI Rematch — Codex vs Production

This is the real independent AI rematch.

Codex was given the constraints in `AI_PROMPT.md` and was explicitly forbidden
from reading the existing production LLM implementation.

Codex created its own implementation under `ai-version/codex/` and ran:

```text
PYTHONPATH=. pytest -q
5 passed in 0.18s
```

## Difference 1 — Structured output strategy

### Codex

Codex requests a strict `json_schema` response format from the
OpenAI-compatible endpoint.

It therefore pushes more of the output-shape constraint down into the provider
request itself.

### Production

The production version uses provider JSON/structured-output mode and then
performs explicit Pydantic validation.

It also supports both:

```text
openai_compatible
ollama_native
```

### Assessment

Codex's approach is smaller and stricter when the provider fully supports
`json_schema`.

The production approach is more portable across the two tested Ollama
transports and still validates the result independently.

---

## Difference 2 — Repair-context security

### Codex

Codex intentionally does not insert the invalid raw model generation back into
the semantic repair prompt.

Only the validation failure and repair instruction are used.

This reduces the chance that adversarial or injected text generated in the
first response becomes trusted repair context.

### Production

The production implementation keeps the broken output as part of the repair
context so the model can see exactly what it needs to correct.

It compensates with:
- system/user separation
- explicit untrusted-data instructions
- one repair limit
- Pydantic validation
- quarantine after repeated invalid output

### Assessment

Codex made a stronger minimization choice for repair-context exposure.

The production version provides richer repair information but has a larger
attack surface in that specific step.

This is a useful concrete lesson from the rematch.

---

## Difference 3 — Scope and operational reliability

### Codex

Codex built a deliberately small async implementation with:
- FastAPI-compatible router
- Pydantic schema
- OpenAI-compatible Ollama access
- structured output
- exactly one semantic repair
- timeout handling
- transient transport retry
- exponential backoff
- jitter / Retry-After behavior
- kill switch
- structured logging hooks
- prompt-injection-aware message separation

### Production

The production implementation additionally contains:
- versioned prompt files
- two provider implementations
- provider abstraction
- quarantine logging
- token-budget preflight
- token/cost accounting
- 10k/day cost projection
- trusted-response cache
- deterministic category-to-team mapping
- v1/v2/v3 prompt experiments
- 8-case required evaluation
- 25-case easy/hard/adversarial evaluation
- five prompt-injection attacks
- two-model latency/accuracy race
- 87 production tests

### Assessment

Codex produced a cleaner minimal architecture.

The production version is larger because it accumulated safeguards from real
evaluation failures and the assignment stretch requirements.

## What the Codex version did better

The most valuable independent idea was:

```text
Do not place invalid generated model text back into the repair prompt.
```

That reduces repair-context injection exposure and is worth considering in a
future production revision.

## What the production version did better

The production implementation has much stronger empirical evidence:

```text
Required 8-case v2 eval : 100%
25-case stretch eval    : 92%
Injection cases         : 5/5 on selected v2
Full production tests   : 87 passed
```

It also supports more operational controls and two real provider transports.

## Final rematch conclusion

The independent Codex solution confirms that the core architecture can be much
smaller while still satisfying the central LLM-safety contract.

The production version remains the stronger submission because it contains
measured reliability, evaluation, observability, provider switching, caching,
and cost controls.

The strongest idea learned from Codex is minimizing untrusted generated text
inside the repair context.
