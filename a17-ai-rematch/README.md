# Independent AI triage

This directory contains an independent FastAPI implementation of `POST /ai/triage`.
It uses an OpenAI-compatible endpoint (including local Ollama), strict structured output,
schema validation, one semantic repair attempt, and narrowly scoped transport retries.

Run from this directory:

```bash
PYTHONPATH=. pytest -q
LLM_ENABLED=true LLM_BASE_URL=http://localhost:11434/v1 uvicorn triage.api:app
```

To integrate without changing production files, include `triage.api.router` in an existing
FastAPI application. `LLM_ENABLED` defaults to false. Other supported settings mirror the
public environment example: `LLM_API_KEY`, `LLM_MODEL`, `LLM_TIMEOUT_SECONDS`,
`LLM_MAX_RETRIES`, and `LLM_MAX_OUTPUT_TOKENS`.

Provider errors and invalid raw generations are converted to a generic 503 response; raw model
content is never returned to callers.
