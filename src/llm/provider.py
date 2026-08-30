from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import httpx


@dataclass(frozen=True)
class ProviderResponse:
    content: str
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


class LLMProvider(Protocol):
    def complete(
        self,
        *,
        model: str,
        system_prompt: str,
        user_message: str,
        max_tokens: int,
        structured_output: bool = False,
    ) -> ProviderResponse:
        ...


class OpenAICompatibleProvider:
    """
    Provider using an OpenAI-compatible chat/completions API.

    In this project it can point to Ollama's local /v1 endpoint.
    It does NOT mean the request must go to OpenAI's servers.
    """

    def __init__(self, client: Any):
        self.client = client

    @staticmethod
    def _usage_value(
        usage: Any,
        name: str,
    ) -> int:
        if usage is None:
            return 0

        value = getattr(
            usage,
            name,
            None,
        )

        if (
            value is None
            and isinstance(usage, dict)
        ):
            value = usage.get(name)

        return int(value or 0)

    def complete(
        self,
        *,
        model: str,
        system_prompt: str,
        user_message: str,
        max_tokens: int,
        structured_output: bool = False,
    ) -> ProviderResponse:
        kwargs: dict[str, Any] = {
            "model": model,
            "temperature": 0,
            "max_tokens": max_tokens,
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_message,
                },
            ],
        }

        if structured_output:
            kwargs["response_format"] = {
                "type": "json_object",
            }

        response = (
            self.client
            .chat
            .completions
            .create(**kwargs)
        )

        usage = getattr(
            response,
            "usage",
            None,
        )

        input_tokens = self._usage_value(
            usage,
            "prompt_tokens",
        )

        output_tokens = self._usage_value(
            usage,
            "completion_tokens",
        )

        total_tokens = self._usage_value(
            usage,
            "total_tokens",
        )

        if total_tokens == 0:
            total_tokens = (
                input_tokens
                + output_tokens
            )

        message = response.choices[0].message

        content = getattr(
            message,
            "content",
            None,
        ) or ""

        return ProviderResponse(
            content=content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
        )


class OllamaNativeProvider:
    """
    Provider using Ollama's native /api/chat API.
    """

    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: float,
    ):
        self.base_url = (
            base_url.rstrip("/")
        )

        self.timeout_seconds = (
            timeout_seconds
        )

    def complete(
        self,
        *,
        model: str,
        system_prompt: str,
        user_message: str,
        max_tokens: int,
        structured_output: bool = False,
    ) -> ProviderResponse:
        payload: dict[str, Any] = {
            "model": model,
            "stream": False,
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_message,
                },
            ],
            "options": {
                "temperature": 0,
                "num_predict": max_tokens,
            },
        }

        if structured_output:
            payload["format"] = "json"

        response = httpx.post(
            f"{self.base_url}/api/chat",
            timeout=self.timeout_seconds,
            json=payload,
        )

        response.raise_for_status()

        data = response.json()

        input_tokens = int(
            data.get(
                "prompt_eval_count",
                0,
            )
            or 0
        )

        output_tokens = int(
            data.get(
                "eval_count",
                0,
            )
            or 0
        )

        content = (
            data
            .get("message", {})
            .get("content", "")
            or ""
        )

        return ProviderResponse(
            content=content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=(
                input_tokens
                + output_tokens
            ),
        )
