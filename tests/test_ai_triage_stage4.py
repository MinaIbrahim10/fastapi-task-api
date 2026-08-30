import os
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

import main
from src.llm.client import (
    LLMUnavailableError,
    _is_retryable,
)


client = TestClient(main.app)


def test_kill_switch_returns_503_without_model_call():
    old_stub = os.environ.get("LLM_STUB")
    old_enabled = os.environ.get("LLM_ENABLED")

    os.environ["LLM_STUB"] = "0"
    os.environ["LLM_ENABLED"] = "false"

    try:
        with patch("main.call_triage_model") as mocked:
            response = client.post(
                "/ai/triage",
                json={"text": "The API is broken."},
            )

        assert response.status_code == 503
        assert response.json()["error"] == "LLM feature disabled"
        mocked.assert_not_called()

    finally:
        if old_stub is None:
            os.environ.pop("LLM_STUB", None)
        else:
            os.environ["LLM_STUB"] = old_stub

        if old_enabled is None:
            os.environ.pop("LLM_ENABLED", None)
        else:
            os.environ["LLM_ENABLED"] = old_enabled


def test_timeout_becomes_504():
    old_stub = os.environ.get("LLM_STUB")
    old_enabled = os.environ.get("LLM_ENABLED")

    os.environ["LLM_STUB"] = "0"
    os.environ["LLM_ENABLED"] = "true"

    try:
        with patch(
            "main.call_triage_model",
            side_effect=LLMUnavailableError("timeout"),
        ):
            response = client.post(
                "/ai/triage",
                json={"text": "Some valid message"},
            )

        assert response.status_code == 504
        assert response.json()["error"] == "LLM timeout"

    finally:
        if old_stub is None:
            os.environ.pop("LLM_STUB", None)
        else:
            os.environ["LLM_STUB"] = old_stub

        if old_enabled is None:
            os.environ.pop("LLM_ENABLED", None)
        else:
            os.environ["LLM_ENABLED"] = old_enabled


def test_provider_failure_becomes_503():
    old_stub = os.environ.get("LLM_STUB")
    old_enabled = os.environ.get("LLM_ENABLED")

    os.environ["LLM_STUB"] = "0"
    os.environ["LLM_ENABLED"] = "true"

    try:
        with patch(
            "main.call_triage_model",
            side_effect=LLMUnavailableError("provider unavailable"),
        ):
            response = client.post(
                "/ai/triage",
                json={"text": "Some valid message"},
            )

        assert response.status_code == 503
        assert response.json()["error"] == "LLM provider unavailable"

    finally:
        if old_stub is None:
            os.environ.pop("LLM_STUB", None)
        else:
            os.environ["LLM_STUB"] = old_stub

        if old_enabled is None:
            os.environ.pop("LLM_ENABLED", None)
        else:
            os.environ["LLM_ENABLED"] = old_enabled


def test_400_is_not_retryable():
    exc = SimpleNamespace(status_code=400)
    assert _is_retryable(exc) is False


def test_401_is_not_retryable():
    exc = SimpleNamespace(status_code=401)
    assert _is_retryable(exc) is False


def test_403_is_not_retryable():
    exc = SimpleNamespace(status_code=403)
    assert _is_retryable(exc) is False
