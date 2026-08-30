import os

from fastapi.testclient import TestClient

import main


client = TestClient(main.app)


def setup_function():
    os.environ["LLM_STUB"] = "1"


def test_stub_valid_request_returns_200():
    response = client.post(
        "/ai/triage",
        json={"text": "The dashboard crashes when I open reports."},
    )

    assert response.status_code == 200

    body = response.json()

    assert body["category"] in {
        "bug", "feature", "account", "billing", "security", "other"
    }
    assert body["urgency"] in {"low", "normal", "high", "critical"}
    assert body["suggested_team"] in {
        "engineering", "product", "support", "billing", "security"
    }
    assert 0.0 <= body["confidence"] <= 1.0
    assert isinstance(body["needs_review"], bool)
    assert isinstance(body["reason"], str)


def test_missing_text_returns_400_and_names_field():
    response = client.post("/ai/triage", json={})

    assert response.status_code == 400
    body = response.json()

    assert body["field"] == "text"


def test_empty_text_returns_400():
    response = client.post("/ai/triage", json={"text": ""})

    assert response.status_code == 400
    assert response.json()["field"] == "text"


def test_text_over_limit_returns_400():
    response = client.post("/ai/triage", json={"text": "x" * 2001})

    assert response.status_code == 400
    assert response.json()["field"] == "text"


def test_wrong_type_returns_400():
    response = client.post("/ai/triage", json={"text": 123})

    assert response.status_code == 400
    assert response.json()["field"] == "text"


def test_extra_field_is_rejected():
    response = client.post(
        "/ai/triage",
        json={
            "text": "Please add dark mode.",
            "admin": True,
        },
    )

    assert response.status_code == 400
    assert response.json()["field"] == "admin"


def test_stub_shape_is_deterministic():
    payload = {"text": "I was charged twice."}

    first = client.post("/ai/triage", json=payload)
    second = client.post("/ai/triage", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()


def test_stub_does_not_require_model():
    old = os.environ.get("LLM_MODEL")
    os.environ["LLM_MODEL"] = "definitely-not-a-real-model"

    try:
        response = client.post(
            "/ai/triage",
            json={"text": "My account login no longer works."},
        )

        assert response.status_code == 200
    finally:
        if old is None:
            os.environ.pop("LLM_MODEL", None)
        else:
            os.environ["LLM_MODEL"] = old
