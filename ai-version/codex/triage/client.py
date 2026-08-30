import asyncio
import json
import logging
import random
import time
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from .models import TriageResult
from .prompt import REPAIR_PROMPT, SYSTEM_PROMPT, user_message

logger = logging.getLogger("ai.triage")


class TriageUnavailable(Exception):
    """Safe public failure: no provider details or raw output attached."""


@dataclass(frozen=True)
class Settings:
    base_url: str = "http://localhost:11434/v1"
    api_key: str = "ollama"
    model: str = "gemma4:e4b-it"
    timeout_seconds: float = 30.0
    max_retries: int = 3
    max_output_tokens: int = 1024


class TriageClient:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings
        self._http = httpx.AsyncClient(
            base_url=settings.base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {settings.api_key}"},
            timeout=httpx.Timeout(settings.timeout_seconds),
            transport=transport,
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    async def classify(self, text: str) -> TriageResult:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message(text)},
        ]
        first = await self._completion(messages, phase="initial")
        try:
            return TriageResult.model_validate_json(first)
        except (ValueError, TypeError):
            # Do not echo invalid output into the repair prompt; it may contain injected text.
            repair_messages = messages + [{"role": "system", "content": REPAIR_PROMPT}]
            repaired = await self._completion(repair_messages, phase="repair")
            try:
                return TriageResult.model_validate_json(repaired)
            except (ValueError, TypeError) as exc:
                raise TriageUnavailable("classification validation failed") from exc

    async def _completion(self, messages: list[dict[str, str]], phase: str) -> str:
        schema = TriageResult.model_json_schema()
        payload = {
            "model": self.settings.model,
            "messages": messages,
            "temperature": 0,
            "max_tokens": self.settings.max_output_tokens,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "support_triage", "strict": True, "schema": schema},
            },
        }
        started = time.monotonic()
        response = await self._post_with_retries(payload)
        duration_ms = round((time.monotonic() - started) * 1000, 1)
        try:
            body: dict[str, Any] = response.json()
            content = body["choices"][0]["message"]["content"]
            if not isinstance(content, str):
                raise TypeError
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise TriageUnavailable("provider response malformed") from exc
        usage = body.get("usage", {})
        logger.info(
            "triage_llm_call",
            extra={
                "event": "triage_llm_call",
                "phase": phase,
                "duration_ms": duration_ms,
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens"),
                "total_tokens": usage.get("total_tokens"),
            },
        )
        return content

    async def _post_with_retries(self, payload: dict[str, Any]) -> httpx.Response:
        for attempt in range(self.settings.max_retries + 1):
            try:
                response = await self._http.post("/chat/completions", json=payload)
                if response.status_code < 400:
                    return response
                retryable = response.status_code == 429 or response.status_code >= 500
                if not retryable:
                    raise TriageUnavailable("provider rejected request")
                if attempt == self.settings.max_retries:
                    raise TriageUnavailable("provider temporarily unavailable")
                delay = self._retry_delay(attempt, response.headers.get("Retry-After"))
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                if attempt == self.settings.max_retries:
                    raise TriageUnavailable("provider temporarily unavailable") from exc
                delay = self._retry_delay(attempt, None)
            await asyncio.sleep(delay)
        raise TriageUnavailable("provider temporarily unavailable")

    @staticmethod
    def _retry_delay(attempt: int, retry_after: str | None) -> float:
        if retry_after:
            try:
                return max(0.0, min(float(retry_after), 60.0))
            except ValueError:
                try:
                    seconds = parsedate_to_datetime(retry_after).timestamp() - time.time()
                    return max(0.0, min(seconds, 60.0))
                except (TypeError, ValueError, OverflowError):
                    pass
        return min(0.25 * (2**attempt), 8.0) + random.uniform(0.0, 0.2)
