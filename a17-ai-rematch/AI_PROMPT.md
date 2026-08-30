You are doing an independent AI rematch for a backend engineering assignment.

IMPORTANT:
This repository already contains a completed production implementation.
You must NOT inspect or copy the existing A17 implementation.

Your goal is to independently build your own solution from the assignment requirements.

You are allowed to inspect only:
- JOB-CARD.md
- README.md only for public API contract and environment/run context
- .env.example
- requirements.txt

You are NOT allowed to inspect:
- src/llm/**
- prompts/**
- evals/**
- tests/test_ai_triage_*
- ai-version/**
- git diff
- git log/history related to A17
- any previous implementation details

Do not infer the hidden implementation from filenames or history.

Build your independent solution only inside:

ai-version/codex/

Do not modify any production file outside that directory.

Task:
Implement an independent LLM-backed support triage workflow compatible with the project.

API behavior:
POST /ai/triage

Input:
{
  "text": "support message"
}

Output must contain:
- category: bug | feature | account | billing | security | other
- urgency: low | normal | high | critical
- suggested_team: engineering | product | support | billing | security
- confidence: float between 0 and 1
- needs_review: boolean
- reason: one short sentence

Requirements:
- use Python
- use FastAPI/Pydantic-compatible models
- support local Ollama
- separate system instructions from user input
- treat user input as untrusted data
- use structured JSON output where supported
- validate all model output
- never expose raw model output directly to the API caller
- exactly one repair attempt if model output is invalid
- fail safely if the repair also fails
- explicit timeout
- retry only for timeout, connection errors, HTTP 429, and HTTP 5xx
- exponential backoff
- jitter
- Retry-After support where possible
- LLM_ENABLED kill switch
- structured token/duration logging
- basic prompt-injection mitigation
- keep the design independent and reasonably minimal

You may create:
- implementation files
- prompt files
- tests
- README

Everything you create must remain under:

ai-version/codex/

You must run the tests you create.

Do not claim anything passed unless you actually ran it.

Do not modify:
- main.py
- requirements.txt
- .env.example
- production tests
- production LLM files

At the end, print exactly:

1. FILES CREATED
2. TESTS RUN AND EXACT RESULTS
3. KNOWN LIMITATIONS
4. THREE INDEPENDENT DESIGN DECISIONS

The three design decisions must be your own and must not be copied from the production implementation.

Independence matters more than matching the existing solution.
