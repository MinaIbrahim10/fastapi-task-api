# AI Rematch — AI vs Me

This directory is intentionally quarantined from the production implementation.

The AI rematch was asked to design the endpoint independently from memory using
the prompt in `AI_PROMPT.md`.

## AI version

The AI version chose:

- one direct OpenAI-compatible client
- one embedded system prompt
- JSON-object response mode
- Pydantic validation
- one repair attempt
- one minimal `triage()` function

## My production version

The main project evolved through staged testing and real failures and includes:

- versioned prompt files
- OpenAI-compatible and native Ollama provider implementations
- provider abstraction
- structured-output mode
- schema validation
- one repair attempt
- quarantine logging
- timeout / retry / Retry-After logic
- exponential backoff + jitter
- kill switch
- per-call token and latency logging
- token pre-budget
- cost estimation
- trusted-response cache
- deterministic category -> team mapping
- prompt v1/v2/v3 experiments
- 8-case required evaluation
- 25-case stretch evaluation
- five injection attacks
- two-model race

## Three concrete differences

### 1. Provider architecture

AI version:
- directly depends on an OpenAI-compatible client

My version:
- hides provider transport behind an interface
- supports both OpenAI-compatible Ollama and native Ollama

Why mine is stronger:
- transport/provider changes do not affect triage business logic

### 2. Reliability behavior

AI version:
- validates output and performs one repair
- otherwise raises a generic runtime error

My version:
- separates invalid structured output from provider failures
- implements controlled retry rules
- respects Retry-After
- exposes clean 422 / 503 / 504 behavior
- quarantines repeated invalid output

Why mine is stronger:
- failure modes are explicit, observable, and production-safe

### 3. Evidence and iteration

AI version:
- is a clean first-pass design
- has no empirical evaluation history

My version:
- records the initial 62.5% baseline
- proves the 300 -> 1024 output-token fix
- records v1 87.5%
- records v2 100% on the required 8-case set
- records v2 92% on 25 stretch cases
- records v3 regression
- records model accuracy/latency trade-offs

Why mine is stronger:
- design decisions are backed by measured failures and regressions rather than
  only implementation assumptions

## Rematch conclusion

The AI version is substantially smaller and easier to read.

The production version is intentionally more complex because real evaluation
showed failure modes that the minimal implementation does not cover.

The best lesson from the rematch is not that more code is always better:
the smallest design is useful as a baseline, but production reliability should
be added only when a real failure mode or explicit requirement justifies it.
