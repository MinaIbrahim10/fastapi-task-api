import json
import os
import random
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    OpenAI,
    RateLimitError,
)
from pydantic import ValidationError

from .schema import TriageResponse


ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

PROMPT_FILES = {
    "v1": ROOT / "prompts" / "triage-v1.md",
}

QUARANTINE_PATH = ROOT / "logs" / "quarantine.jsonl"
COST_LOG_PATH = ROOT / "logs" / "llm-calls.jsonl"


class TriageOutputError(RuntimeError):
    pass


class LLMUnavailableError(RuntimeError):
    pass


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


def _extract_json_object(raw: str) -> dict[str, Any]:
    text = raw.strip()

    if not text:
        raise ValueError("Model returned an empty response")

    if text.startswith("```"):
        lines = text.splitlines()

        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        text = "\n".join(lines).strip()

    try:
        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            raise ValueError("Model output must be a JSON object")
        return parsed
    except json.JSONDecodeError:
        pass

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


def _retry_after_seconds(exc: Exception) -> float | None:
    response = getattr(exc, "response", None)

    if response is None:
        return None

    value = response.headers.get("retry-after")

    if not value:
        return None

    try:
        return max(0.0, float(value))
    except ValueError:
        pass

    try:
        retry_at = parsedate_to_datetime(value)

        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=timezone.utc)

        return max(
            0.0,
            (retry_at - datetime.now(timezone.utc)).total_seconds(),
        )
    except Exception:
        return None


def _is_retryable(exc: Exception) -> bool:
    if isinstance(exc, (APITimeoutError, APIConnectionError, RateLimitError)):
        return True

    if isinstance(exc, APIStatusError):
        return exc.status_code >= 500

    return False


def _usage_value(usage: Any, name: str) -> int:
    if usage is None:
        return 0

    value = getattr(usage, name, None)

    if value is None and isinstance(usage, dict):
        value = usage.get(name)

    return int(value or 0)


def _write_cost_log(
    *,
    model: str,
    prompt_version: str,
    usage: Any,
    duration_ms: int,
    repair_count: int,
    attempts: int,
) -> None:
    COST_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "prompt_version": prompt_version,
        "model": model,
        "input_tokens": _usage_value(usage, "prompt_tokens"),
        "output_tokens": _usage_value(usage, "completion_tokens"),
        "total_tokens": _usage_value(usage, "total_tokens"),
        "duration_ms": duration_ms,
        "repair_count": repair_count,
        "transport_attempts": attempts,
    }

    with COST_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _call_model(
    *,
    system_prompt: str,
    user_message: str,
    repair_count: int,
) -> str:
    model = os.environ["LLM_MODEL"]
    prompt_version = get_prompt_version()

    max_retries = int(os.getenv("LLM_MAX_RETRIES", "3"))

    last_exc: Exception | None = None

    for attempt in range(max_retries + 1):
        started = time.perf_counter()

        try:
            response = build_client().chat.completions.create(
                model=model,
                temperature=0,
                max_tokens=1024,
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

            duration_ms = int(
                (time.perf_counter() - started) * 1000
            )

            _write_cost_log(
                model=model,
                prompt_version=prompt_version,
                usage=getattr(response, "usage", None),
                duration_ms=duration_ms,
                repair_count=repair_count,
                attempts=attempt + 1,
            )

            return response.choices[0].message.content or ""

        except Exception as exc:
            last_exc = exc

            if not _is_retryable(exc):
                raise

            if attempt >= max_retries:
                break

            retry_after = _retry_after_seconds(exc)

            if retry_after is not None:
                delay = retry_after
            else:
                delay = (2 ** attempt) + random.uniform(0.0, 0.25)

            time.sleep(delay)

    if isinstance(last_exc, APITimeoutError):
        raise LLMUnavailableError("timeout") from last_exc

    raise LLMUnavailableError("provider unavailable") from last_exc


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
        repair_count=1,
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
        repair_count=0,
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
