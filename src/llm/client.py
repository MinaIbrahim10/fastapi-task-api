import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import ValidationError

from .schema import TriageResponse


ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

PROMPT_FILES = {
    "v1": ROOT / "prompts" / "triage-v1.md",
}

QUARANTINE_PATH = ROOT / "logs" / "quarantine.jsonl"


class TriageOutputError(RuntimeError):
    """Raised when the model fails schema validation even after one repair."""


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
        # We own the retry policy. Stage 4 will add selective transport retries.
        max_retries=0,
    )


def _extract_json_object(raw: str) -> dict[str, Any]:
    """
    Recover one JSON object from common LLM formatting mistakes.

    Accepted:
    - raw JSON
    - ```json ... ``` fences
    - explanatory text before/after the JSON

    This function does NOT make invalid schema values valid.
    """

    text = raw.strip()

    if not text:
        raise ValueError("Model returned an empty response")

    # Remove a common Markdown fence wrapper.
    if text.startswith("```"):
        lines = text.splitlines()

        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        text = "\n".join(lines).strip()

    # Fast path: exactly one JSON document.
    try:
        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            raise ValueError("Model output must be a JSON object")
        return parsed
    except json.JSONDecodeError:
        pass

    # Recovery path: locate the first object and let JSONDecoder determine
    # where that object actually ends. Any prose around it is ignored.
    start = text.find("{")

    if start == -1:
        raise ValueError("No JSON object found in model response")

    decoder = json.JSONDecoder()

    try:
        parsed, _ = decoder.raw_decode(text[start:])
    except json.JSONDecodeError as exc:
        raise ValueError(f"Could not parse JSON object: {exc}") from exc

    if not isinstance(parsed, dict):
        raise ValueError("Model output must be a JSON object")

    return parsed


def _parse_and_validate(raw: str) -> TriageResponse:
    parsed = _extract_json_object(raw)
    return TriageResponse.model_validate(parsed)


def _validation_message(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        return json.dumps(
            exc.errors(include_url=False),
            ensure_ascii=False,
        )

    return str(exc)


def _call_model(
    *,
    system_prompt: str,
    user_message: str,
) -> str:
    response = build_client().chat.completions.create(
        model=os.environ["LLM_MODEL"],
        temperature=0,
        max_tokens=300,
        messages=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": user_message,
            },
        ],
    )

    return response.choices[0].message.content or ""


def _repair_once(
    *,
    system_prompt: str,
    user_payload: str,
    broken_output: str,
    error: str,
) -> str:
    repair_message = json.dumps(
        {
            "original_input": json.loads(user_payload),
            "previous_output": broken_output,
            "validation_error": error,
            "instruction": (
                "Your previous answer was rejected. "
                "Return ONLY one corrected JSON object matching the required "
                "schema. Do not add Markdown or explanation."
            ),
        },
        ensure_ascii=False,
    )

    return _call_model(
        system_prompt=system_prompt,
        user_message=repair_message,
    )


def _write_quarantine(
    *,
    input_text: str,
    first_raw: str,
    final_raw: str,
    error: str,
    prompt_version: str,
) -> None:
    QUARANTINE_PATH.parent.mkdir(parents=True, exist_ok=True)

    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "prompt_version": prompt_version,
        "input": input_text,
        "error": error,
        "first_model_output": first_raw,
        "final_model_output": final_raw,
        "repair_attempts": 1,
    }

    with QUARANTINE_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def call_triage_model(text: str) -> TriageResponse:
    """
    Production trust boundary:

    1. User data is JSON-encoded and kept outside the system prompt.
    2. First model response is parsed and schema-validated.
    3. On failure, exactly ONE repair request is made.
    4. If repair still fails, output is quarantined and a safe exception
       reaches the API layer.
    """

    prompt_version = get_prompt_version()
    system_prompt = load_system_prompt(prompt_version)

    user_payload = json.dumps(
        {
            "source": "untrusted_support_message",
            "text": text,
        },
        ensure_ascii=False,
    )

    first_raw = _call_model(
        system_prompt=system_prompt,
        user_message=user_payload,
    )

    try:
        return _parse_and_validate(first_raw)
    except (ValueError, ValidationError) as first_exc:
        first_error = _validation_message(first_exc)

    repaired_raw = _repair_once(
        system_prompt=system_prompt,
        user_payload=user_payload,
        broken_output=first_raw,
        error=first_error,
    )

    try:
        return _parse_and_validate(repaired_raw)
    except (ValueError, ValidationError) as final_exc:
        final_error = _validation_message(final_exc)

        _write_quarantine(
            input_text=text,
            first_raw=first_raw,
            final_raw=repaired_raw,
            error=final_error,
            prompt_version=prompt_version,
        )

        raise TriageOutputError(
            "The model could not produce a valid triage response "
            "after one repair attempt."
        ) from final_exc
