import json
from types import SimpleNamespace
from unittest.mock import patch

from src.llm.cache import TriageCache, triage_cache
from src.llm.client import call_triage_model
from src.llm.provider import OpenAICompatibleProvider


VALID_JSON = json.dumps(
    {
        "category": "bug",
        "urgency": "high",
        "suggested_team": "engineering",
        "confidence": 0.95,
        "needs_review": False,
        "reason": "The application crashes.",
    }
)


class FakeCompletions:
    def __init__(self):
        self.calls = 0

    def create(self, **kwargs):
        self.calls += 1

        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=VALID_JSON
                    )
                )
            ],
            usage=SimpleNamespace(
                prompt_tokens=10,
                completion_tokens=5,
                total_tokens=15,
            ),
        )


class FakeClient:
    def __init__(self):
        self.completions = FakeCompletions()
        self.chat = SimpleNamespace(
            completions=self.completions
        )


def test_cache_key_changes_with_prompt_version():
    cache = TriageCache()

    a = cache.build_key(
        text="same",
        prompt_version="v1",
        model="m",
        provider="p",
    )

    b = cache.build_key(
        text="same",
        prompt_version="v2",
        model="m",
        provider="p",
    )

    assert a != b


def test_cache_key_changes_with_model():
    cache = TriageCache()

    a = cache.build_key(
        text="same",
        prompt_version="v2",
        model="model-a",
        provider="p",
    )

    b = cache.build_key(
        text="same",
        prompt_version="v2",
        model="model-b",
        provider="p",
    )

    assert a != b


def test_cache_key_changes_with_provider():
    cache = TriageCache()

    a = cache.build_key(
        text="same",
        prompt_version="v2",
        model="m",
        provider="provider-a",
    )

    b = cache.build_key(
        text="same",
        prompt_version="v2",
        model="m",
        provider="provider-b",
    )

    assert a != b


def test_second_identical_request_avoids_llm(
    monkeypatch,
):
    triage_cache.clear()

    monkeypatch.setenv(
        "LLM_CACHE_ENABLED",
        "true",
    )
    monkeypatch.setenv(
        "LLM_CACHE_TTL_SECONDS",
        "300",
    )
    monkeypatch.setenv(
        "LLM_MODEL",
        "fake-model",
    )
    monkeypatch.setenv(
        "LLM_PROVIDER",
        "openai_compatible",
    )
    monkeypatch.setenv(
        "LLM_PROMPT_VERSION",
        "v2",
    )

    fake = FakeClient()

    with patch(
        "src.llm.client.build_provider",
        return_value=OpenAICompatibleProvider(fake),
    ):
        first = call_triage_model(
            "The app crashes."
        )

        second = call_triage_model(
            "The app crashes."
        )

    assert first == second
    assert fake.completions.calls == 1


def test_disabled_cache_calls_llm_twice(
    monkeypatch,
):
    triage_cache.clear()

    monkeypatch.setenv(
        "LLM_CACHE_ENABLED",
        "false",
    )
    monkeypatch.setenv(
        "LLM_MODEL",
        "fake-model",
    )
    monkeypatch.setenv(
        "LLM_PROVIDER",
        "openai_compatible",
    )
    monkeypatch.setenv(
        "LLM_PROMPT_VERSION",
        "v2",
    )

    fake = FakeClient()

    with patch(
        "src.llm.client.build_provider",
        return_value=OpenAICompatibleProvider(fake),
    ):
        call_triage_model(
            "The app crashes."
        )

        call_triage_model(
            "The app crashes."
        )

    assert fake.completions.calls == 2
