from types import SimpleNamespace
from unittest.mock import patch

import httpx
import pytest

from src.llm import client as llm_client
from src.llm.provider import (
    OllamaNativeProvider,
    OpenAICompatibleProvider,
    ProviderResponse,
)


class FakeOpenAIClient:
    def __init__(self):
        self.chat = SimpleNamespace(
            completions=self
        )

    def create(self, **kwargs):
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content='{"ok":true}'
                    )
                )
            ],
            usage=SimpleNamespace(
                prompt_tokens=10,
                completion_tokens=5,
                total_tokens=15,
            ),
        )


def test_openai_compatible_provider_normalizes_response():
    provider = OpenAICompatibleProvider(
        FakeOpenAIClient()
    )

    result = provider.complete(
        model="test-model",
        system_prompt="system",
        user_message="user",
        max_tokens=100,
    )

    assert result == ProviderResponse(
        content='{"ok":true}',
        input_tokens=10,
        output_tokens=5,
        total_tokens=15,
    )


def test_build_provider_selects_openai_compatible(
    monkeypatch,
):
    monkeypatch.setenv(
        "LLM_PROVIDER",
        "openai_compatible",
    )

    with patch(
        "src.llm.client.build_client",
        return_value=FakeOpenAIClient(),
    ):
        provider = llm_client.build_provider()

    assert isinstance(
        provider,
        OpenAICompatibleProvider,
    )


def test_build_provider_selects_ollama_native(
    monkeypatch,
):
    monkeypatch.setenv(
        "LLM_PROVIDER",
        "ollama_native",
    )
    monkeypatch.setenv(
        "OLLAMA_BASE_URL",
        "http://localhost:11434",
    )

    provider = llm_client.build_provider()

    assert isinstance(
        provider,
        OllamaNativeProvider,
    )


def test_unknown_provider_is_rejected(
    monkeypatch,
):
    monkeypatch.setenv(
        "LLM_PROVIDER",
        "something-unknown",
    )

    with pytest.raises(
        RuntimeError,
        match="Unsupported LLM_PROVIDER",
    ):
        llm_client.build_provider()


def test_native_429_is_retryable():
    request = httpx.Request(
        "POST",
        "http://localhost/api/chat",
    )

    response = httpx.Response(
        429,
        request=request,
    )

    exc = httpx.HTTPStatusError(
        "rate limited",
        request=request,
        response=response,
    )

    assert llm_client._is_retryable(exc)


def test_native_500_is_retryable():
    request = httpx.Request(
        "POST",
        "http://localhost/api/chat",
    )

    response = httpx.Response(
        500,
        request=request,
    )

    exc = httpx.HTTPStatusError(
        "server error",
        request=request,
        response=response,
    )

    assert llm_client._is_retryable(exc)


def test_native_400_is_not_retryable():
    request = httpx.Request(
        "POST",
        "http://localhost/api/chat",
    )

    response = httpx.Response(
        400,
        request=request,
    )

    exc = httpx.HTTPStatusError(
        "bad request",
        request=request,
        response=response,
    )

    assert not llm_client._is_retryable(exc)
