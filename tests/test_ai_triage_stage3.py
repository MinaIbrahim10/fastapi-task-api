import json
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

import main
from src.llm import client as llm_client
from src.llm.provider import OpenAICompatibleProvider
from src.llm.client import (
    TriageOutputError,
    _extract_json_object,
    call_triage_model,
)


VALID_JSON = json.dumps(
    {
        "category": "bug",
        "urgency": "high",
        "suggested_team": "engineering",
        "confidence": 0.94,
        "needs_review": False,
        "reason": "The message describes a reproducible runtime failure.",
    }
)


def fake_response(content):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=content)
            )
        ]
    )


class FakeCompletions:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = 0

    def create(self, **kwargs):
        self.calls += 1

        if not self.outputs:
            raise AssertionError("Model called more times than expected")

        return fake_response(self.outputs.pop(0))


class FakeClient:
    def __init__(self, outputs):
        self.chat = SimpleNamespace(
            completions=FakeCompletions(outputs)
        )


def test_parser_accepts_plain_json():
    parsed = _extract_json_object(VALID_JSON)

    assert parsed["category"] == "bug"


def test_parser_accepts_markdown_json_fence():
    raw = f"```json\n{VALID_JSON}\n```"

    parsed = _extract_json_object(raw)

    assert parsed["suggested_team"] == "engineering"


def test_parser_accepts_text_around_json():
    raw = f"Here is the result:\n{VALID_JSON}\nDone."

    parsed = _extract_json_object(raw)

    assert parsed["urgency"] == "high"


def test_invalid_first_answer_repairs_exactly_once():
    fake = FakeClient(
        [
            "This is not JSON.",
            VALID_JSON,
        ]
    )

    with patch("src.llm.client.build_provider", return_value=OpenAICompatibleProvider(fake)):
        result = call_triage_model("The API crashes on startup.")

    assert result.category == "bug"
    assert fake.chat.completions.calls == 2


def test_invalid_enum_repairs_once():
    invalid = json.dumps(
        {
            "category": "banana",
            "urgency": "normal",
            "suggested_team": "support",
            "confidence": 0.5,
            "needs_review": True,
            "reason": "Invalid category.",
        }
    )

    fake = FakeClient([invalid, VALID_JSON])

    with patch("src.llm.client.build_provider", return_value=OpenAICompatibleProvider(fake)):
        result = call_triage_model("Something broke.")

    assert result.category == "bug"
    assert fake.chat.completions.calls == 2


def test_second_failure_quarantines_and_stops(tmp_path):
    fake = FakeClient(
        [
            "not-json-one",
            "not-json-two",
        ]
    )

    quarantine = tmp_path / "quarantine.jsonl"

    with (
        patch("src.llm.client.build_provider", return_value=OpenAICompatibleProvider(fake)),
        patch.object(llm_client, "QUARANTINE_PATH", quarantine),
    ):
        with pytest.raises(TriageOutputError):
            call_triage_model("Impossible input")

    assert fake.chat.completions.calls == 2
    assert quarantine.exists()

    rows = quarantine.read_text().splitlines()

    assert len(rows) == 1

    record = json.loads(rows[0])

    assert record["prompt_version"] == llm_client.get_prompt_version()
    assert record["repair_attempts"] == 1
    assert record["input"] == "Impossible input"
    assert "error" in record


def test_api_turns_unrepairable_output_into_422():
    api = TestClient(main.app)

    old_stub = main.os.environ.get("LLM_STUB")
    main.os.environ["LLM_STUB"] = "0"

    try:
        with patch(
            "main.call_triage_model",
            side_effect=TriageOutputError("broken"),
        ):
            response = api.post(
                "/ai/triage",
                json={"text": "Some valid input"},
            )
    finally:
        if old_stub is None:
            main.os.environ.pop("LLM_STUB", None)
        else:
            main.os.environ["LLM_STUB"] = old_stub

    assert response.status_code == 422
    assert response.json()["error"] == "LLM output validation failed"


def test_raw_model_text_never_appears_in_422():
    api = TestClient(main.app)

    secret_raw = "RAW MODEL CONTENT THAT MUST NOT LEAK"

    old_stub = main.os.environ.get("LLM_STUB")
    main.os.environ["LLM_STUB"] = "0"

    try:
        with patch(
            "main.call_triage_model",
            side_effect=TriageOutputError(secret_raw),
        ):
            response = api.post(
                "/ai/triage",
                json={"text": "Valid input"},
            )
    finally:
        if old_stub is None:
            main.os.environ.pop("LLM_STUB", None)
        else:
            main.os.environ["LLM_STUB"] = old_stub

    assert response.status_code == 422
    assert secret_raw not in response.text
