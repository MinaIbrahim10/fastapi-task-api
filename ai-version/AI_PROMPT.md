# AI Rematch Prompt

You are implementing one production-style FastAPI endpoint backed by an LLM.

Task:
Build a POST /ai/triage endpoint that accepts one support message and returns
strict structured JSON with these fields:

- category: bug | feature | account | billing | security | other
- urgency: low | normal | high | critical
- suggested_team: engineering | product | support | billing | security
- confidence: float 0..1
- needs_review: boolean
- reason: one short sentence

Requirements:
- FastAPI + Pydantic
- user input must be treated as untrusted data
- prompt must be versioned
- no raw model text may be returned
- parse + validate model output
- exactly one repair attempt on invalid output
- second invalid output must fail safely
- timeout support
- retry only timeout / connection / 429 / 5xx
- exponential backoff + jitter
- Retry-After support
- LLM_ENABLED kill switch
- token / latency logging
- prompt injection mitigation
- structured JSON output where provider supports it
- local Ollama-compatible model
- keep implementation simple enough to review

Do not copy the existing project implementation.
Produce an independent minimal design from memory.
