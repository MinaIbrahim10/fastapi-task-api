import os

from fastapi import APIRouter, FastAPI, HTTPException, Request

from .client import Settings, TriageClient, TriageUnavailable
from .models import TriageRequest, TriageResult

router = APIRouter()


def _enabled() -> bool:
    return os.getenv("LLM_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}


def settings_from_env() -> Settings:
    return Settings(
        base_url=os.getenv("LLM_BASE_URL", "http://localhost:11434/v1"),
        api_key=os.getenv("LLM_API_KEY", "ollama"),
        model=os.getenv("LLM_MODEL", "gemma4:e4b-it"),
        timeout_seconds=float(os.getenv("LLM_TIMEOUT_SECONDS", "30")),
        max_retries=max(0, int(os.getenv("LLM_MAX_RETRIES", "3"))),
        max_output_tokens=max(1, int(os.getenv("LLM_MAX_OUTPUT_TOKENS", "1024"))),
    )


@router.post("/ai/triage", response_model=TriageResult)
async def triage(payload: TriageRequest, request: Request) -> TriageResult:
    if not _enabled():
        raise HTTPException(status_code=503, detail="AI triage is disabled")
    client = getattr(request.app.state, "triage_client", None)
    owns_client = client is None
    if client is None:
        client = TriageClient(settings_from_env())
    try:
        return await client.classify(payload.text)
    except TriageUnavailable:
        raise HTTPException(status_code=503, detail="AI triage is temporarily unavailable") from None
    finally:
        if owns_client:
            await client.aclose()


app = FastAPI(title="Independent AI Support Triage")
app.include_router(router)
