import json
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from .schema import TriageResponse


ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

PROMPT_FILES = {
    "v1": ROOT / "prompts" / "triage-v1.md",
}


def get_prompt_version() -> str:
    return os.getenv("LLM_PROMPT_VERSION", "v1")


def load_system_prompt(version: str | None = None) -> str:
    version = version or get_prompt_version()

    try:
        path = PROMPT_FILES[version]
    except KeyError as exc:
        raise RuntimeError(f"Unsupported prompt version: {version}") from exc

    return path.read_text(encoding="utf-8")


def build_client() -> OpenAI:
    return OpenAI(
        base_url=os.environ["LLM_BASE_URL"],
        api_key=os.environ["LLM_API_KEY"],
        timeout=float(os.getenv("LLM_TIMEOUT_SECONDS", "30")),
        max_retries=0,
    )


def call_triage_model(text: str) -> TriageResponse:
    """
    Stage 2 implementation.

    The user's content is sent as a separate user message and JSON-encoded.
    Stage 3 will add robust extraction, validation repair, and quarantine.
    """

    prompt = load_system_prompt()

    # Important prompt-injection boundary:
    # user-controlled content is data inside a separate user message.
    user_payload = json.dumps(
        {"text": text},
        ensure_ascii=False,
    )

    response = build_client().chat.completions.create(
        model=os.environ["LLM_MODEL"],
        temperature=0,
        max_tokens=250,
        messages=[
            {
                "role": "system",
                "content": prompt,
            },
            {
                "role": "user",
                "content": user_payload,
            },
        ],
    )

    raw = response.choices[0].message.content or ""

    # Minimal Stage-2 parser.
    # Stage 3 will deliberately replace this with the full
    # parse -> validate -> repair once -> quarantine pipeline.
    parsed = json.loads(raw.strip())

    return TriageResponse.model_validate(parsed)
