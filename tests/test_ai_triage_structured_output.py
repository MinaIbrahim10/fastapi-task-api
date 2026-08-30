import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from src.llm.client import (
    TriageOutputError,
    _looks_like_refusal,
    call_triage_model,
)
from src.llm.provider import OpenAICompatibleProvider


VALID_JSON = json.dumps(
    {
        "category": "other",
        "urgency": "low",
        "suggested_team": "support",
        "confidence": 0.8,
        "needs_review": False,
        "reason": "General support request.",
    }
)


class FakeCompletions:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = 0
        self.kwargs = []

    def create(self, **kwargs):
        self.kwargs.append(kwargs)

        output = self.outputs[self.calls]
        self.calls += 1

        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=output
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
    def __init__(self, outputs):
        self.completions = FakeCompletions(outputs)
        self.chat = SimpleNamespace(
            completions=self.completions
        )


def test_refusal_detection():
    assert _looks_like_refusal(
        "I cannot comply with that request."
    )

    assert not _looks_like_refusal(
        '{"category":"other"}'
    )


def test_structured_output_requests_json_object(
    monkeypatch,
):
    monkeypatch.setenv(
        "LLM_STRUCTURED_OUTPUT",
        "true",
    )
    monkeypatch.setenv(
        "LLM_CACHE_ENABLED",
        "false",
    )
    monkeypatch.setenv(
        "LLM_MODEL",
        "fake",
    )
    monkeypatch.setenv(
        "LLM_PROVIDER",
        "openai_compatible",
    )
    monkeypatch.setenv(
        "LLM_PROMPT_VERSION",
        "v2",
    )

    fake = FakeClient([VALID_JSON])

    with patch(
        "src.llm.client.build_provider",
        return_value=OpenAICompatibleProvider(fake),
    ):
        result = call_triage_model(
            "Hello support."
        )

    assert result.category == "other"

    kwargs = fake.completions.kwargs[0]

    assert kwargs["response_format"] == {
        "type": "json_object"
    }


def test_refusal_gets_exactly_one_repair(
    monkeypatch,
):
    monkeypatch.setenv(
        "LLM_STRUCTURED_OUTPUT",
        "true",
    )
    monkeypatch.setenv(
        "LLM_CACHE_ENABLED",
        "false",
    )
    monkeypatch.setenv(
        "LLM_MODEL",
        "fake",
    )
    monkeypatch.setenv(
        "LLM_PROVIDER",
        "openai_compatible",
    )
    monkeypatch.setenv(
        "LLM_PROMPT_VERSION",
        "v2",
    )

    fake = FakeClient(
        [
            "I cannot comply with that request.",
            VALID_JSON,
        ]
    )

    with patch(
        "src.llm.client.build_provider",
        return_value=OpenAICompatibleProvider(fake),
    ):
        result = call_triage_model(
            "A normal support message."
        )

    assert result.category == "other"
    assert fake.completions.calls == 2


def test_two_refusals_fail_safely(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv(
        "LLM_STRUCTURED_OUTPUT",
        "true",
    )
    monkeypatch.setenv(
        "LLM_CACHE_ENABLED",
        "false",
    )
    monkeypatch.setenv(
        "LLM_MODEL",
        "fake",
    )
    monkeypatch.setenv(
        "LLM_PROVIDER",
        "openai_compatible",
    )
    monkeypatch.setenv(
        "LLM_PROMPT_VERSION",
        "v2",
    )

    fake = FakeClient(
        [
            "I cannot comply.",
            "I cannot comply.",
        ]
    )

    from src.llm import client as llm_client

    quarantine = tmp_path / "q.jsonl"

    with (
        patch(
            "src.llm.client.build_provider",
            return_value=OpenAICompatibleProvider(fake),
        ),
        patch.object(
            llm_client,
            "QUARANTINE_PATH",
            quarantine,
        ),
    ):
        with pytest.raises(TriageOutputError):
            call_triage_model(
                "A normal support message."
            )

    assert fake.completions.calls == 2
    assert quarantine.exists()
