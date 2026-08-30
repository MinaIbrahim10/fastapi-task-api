import json
import httpx
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

from .cache import (
    cache_enabled,
    cache_ttl_seconds,
    triage_cache,
)
from .cost import calculate_cost, estimate_tokens
from .provider import (
    LLMProvider,
    OllamaNativeProvider,
    OpenAICompatibleProvider,
)
from .schema import TriageResponse, expected_team_for_category


ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

PROMPT_FILES = {
    "v1": ROOT / "prompts" / "triage-v1.md",
    "v2": ROOT / "prompts" / "triage-v2.md",
    "v3": ROOT / "prompts" / "triage-v3.md",
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


def build_provider() -> LLMProvider:
    provider_name = os.getenv(
        "LLM_PROVIDER",
        "openai_compatible",
    ).strip().lower()

    if provider_name == "openai_compatible":
        return OpenAICompatibleProvider(
            client=build_client(),
        )

    if provider_name == "ollama_native":
        return OllamaNativeProvider(
            base_url=os.getenv(
                "OLLAMA_BASE_URL",
                "http://localhost:11434",
            ),
            timeout_seconds=float(
                os.getenv(
                    "LLM_TIMEOUT_SECONDS",
                    "30",
                )
            ),
        )

    raise RuntimeError(
        f"Unsupported LLM_PROVIDER: {provider_name}"
    )


def _looks_like_refusal(raw: str) -> bool:
    text = raw.strip().lower()

    refusal_markers = (
        "i can't assist",
        "i cannot assist",
        "i can't comply",
        "i cannot comply",
        "i'm unable to",
        "i am unable to",
        "cannot provide",
        "can't provide",
    )

    return any(
        marker in text
        for marker in refusal_markers
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
    if _looks_like_refusal(raw):
        raise ValueError(
            "Model returned a refusal instead of structured output"
        )

    parsed = _extract_json_object(raw)
    response = TriageResponse.model_validate(parsed)

    expected_team = expected_team_for_category(
        response.category
    )

    if response.suggested_team != expected_team:
        response = response.model_copy(
            update={
                "suggested_team": expected_team,
            }
        )

    return response


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

    headers = getattr(response, "headers", None)

    if headers is None:
        return None

    value = headers.get("retry-after")

    if not value:
        return None

    try:
        return max(0.0, float(value))
    except ValueError:
        pass

    try:
        retry_at = parsedate_to_datetime(value)

        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(
                tzinfo=timezone.utc
            )

        return max(
            0.0,
            (
                retry_at
                - datetime.now(timezone.utc)
            ).total_seconds(),
        )
    except Exception:
        return None

def _is_retryable(exc: Exception) -> bool:
    if isinstance(
        exc,
        (
            APITimeoutError,
            APIConnectionError,
            RateLimitError,
            httpx.TimeoutException,
            httpx.ConnectError,
        ),
    ):
        return True

    if isinstance(exc, APIStatusError):
        return exc.status_code >= 500

    if isinstance(exc, httpx.HTTPStatusError):
        status_code = exc.response.status_code
        return status_code == 429 or status_code >= 500

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
    provider: str,
    model: str,
    prompt_version: str,
    input_tokens: int,
    output_tokens: int,
    total_tokens: int,
    estimated_cost_usd: float,
    duration_ms: int,
    repair_count: int,
    attempts: int,
) -> None:
    COST_LOG_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    record = {
        "timestamp": datetime.now(
            timezone.utc
        ).isoformat(),
        "provider": provider,
        "prompt_version": prompt_version,
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "estimated_cost_usd": round(
            estimated_cost_usd,
            10,
        ),
        "duration_ms": duration_ms,
        "repair_count": repair_count,
        "transport_attempts": attempts,
    }

    with COST_LOG_PATH.open(
        "a",
        encoding="utf-8",
    ) as handle:
        handle.write(
            json.dumps(
                record,
                ensure_ascii=False,
            )
            + "\n"
        )

def _call_model(
    *,
    system_prompt: str,
    user_message: str,
    repair_count: int,
) -> str:
    model = os.environ["LLM_MODEL"]
    prompt_version = get_prompt_version()
    provider_name = os.getenv(
        "LLM_PROVIDER",
        "openai_compatible",
    ).strip().lower()

    max_retries = int(
        os.getenv(
            "LLM_MAX_RETRIES",
            "3",
        )
    )

    max_tokens = int(
        os.getenv(
            "LLM_MAX_OUTPUT_TOKENS",
            "1024",
        )
    )

    estimated_input_tokens = estimate_tokens(
        system_prompt + "\n" + user_message
    )

    max_input_tokens = int(
        os.getenv(
            "LLM_MAX_INPUT_TOKENS",
            "4096",
        )
    )

    if estimated_input_tokens > max_input_tokens:
        raise ValueError(
            "Estimated prompt token budget exceeded: "
            f"{estimated_input_tokens} > {max_input_tokens}"
        )

    last_exc: Exception | None = None

    for attempt in range(max_retries + 1):
        started = time.perf_counter()

        try:
            provider = build_provider()

            structured_output = (
                os.getenv(
                    "LLM_STRUCTURED_OUTPUT",
                    "true",
                ).lower()
                == "true"
            )

            response = provider.complete(
                model=model,
                system_prompt=system_prompt,
                user_message=user_message,
                max_tokens=max_tokens,
                structured_output=structured_output,
            )

            duration_ms = int(
                (
                    time.perf_counter()
                    - started
                )
                * 1000
            )

            cost = calculate_cost(
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
            )

            _write_cost_log(
                provider=provider_name,
                model=model,
                prompt_version=prompt_version,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                total_tokens=response.total_tokens,
                estimated_cost_usd=cost.total_cost_usd,
                duration_ms=duration_ms,
                repair_count=repair_count,
                attempts=attempt + 1,
            )

            return response.content

        except Exception as exc:
            last_exc = exc

            if not _is_retryable(exc):
                raise

            if attempt >= max_retries:
                break

            retry_after = _retry_after_seconds(
                exc
            )

            if retry_after is not None:
                delay = retry_after
            else:
                delay = (
                    2 ** attempt
                ) + random.uniform(
                    0.0,
                    0.25,
                )

            time.sleep(delay)

    if isinstance(
        last_exc,
        (
            APITimeoutError,
            httpx.TimeoutException,
        ),
    ):
        raise LLMUnavailableError(
            "timeout"
        ) from last_exc

    raise LLMUnavailableError(
        "provider unavailable"
    ) from last_exc

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
    model = os.environ["LLM_MODEL"]
    provider_name = os.getenv(
        "LLM_PROVIDER",
        "openai_compatible",
    ).strip().lower()

    cache_key = triage_cache.build_key(
        text=text,
        prompt_version=prompt_version,
        model=model,
        provider=provider_name,
    )

    if cache_enabled():
        cached = triage_cache.get(cache_key)

        if cached is not None:
            return TriageResponse.model_validate(cached)

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
        response = _parse_and_validate(first_raw)

        if cache_enabled():
            triage_cache.set(
                cache_key,
                response.model_dump(mode="json"),
                ttl_seconds=cache_ttl_seconds(),
            )

        return response

    except (ValueError, ValidationError) as first_exc:
        first_error = _validation_message(first_exc)

    repaired_raw = _repair_once(
        system_prompt=system_prompt,
        user_payload=user_payload,
        broken_output=first_raw,
        error=first_error,
    )

    try:
        response = _parse_and_validate(repaired_raw)

        if cache_enabled():
            triage_cache.set(
                cache_key,
                response.model_dump(mode="json"),
                ttl_seconds=cache_ttl_seconds(),
            )

        return response

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
