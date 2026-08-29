from types import SimpleNamespace

from fastapi.testclient import TestClient

import main


client = TestClient(main.app)


def fake_user():
    return SimpleNamespace(
        id="user-123",
        email="test@example.com",
        created_at="2026-08-30T00:00:00+00:00",
    )


def test_public_route_requires_no_auth():
    response = client.get("/public/info")

    assert response.status_code == 200
    assert response.json() == {
        "message": "Welcome stranger! This info is public."
    }


def test_protected_route_without_header_returns_401():
    response = client.get("/protected/profile")

    assert response.status_code == 401
    assert response.json() == {
        "error": "Access token required"
    }


def test_protected_route_rejects_wrong_scheme():
    response = client.get(
        "/protected/profile",
        headers={"Authorization": "Basic abc123"},
    )

    assert response.status_code == 401
    assert response.json() == {
        "error": "Access token required"
    }


def test_protected_route_rejects_bearer_without_token():
    response = client.get(
        "/protected/profile",
        headers={"Authorization": "Bearer"},
    )

    assert response.status_code == 401


def test_protected_route_rejects_extra_parts():
    response = client.get(
        "/protected/profile",
        headers={"Authorization": "Bearer token extra"},
    )

    assert response.status_code == 401


def test_valid_token_returns_profile(monkeypatch):
    fake_response = SimpleNamespace(
        user=fake_user(),
    )

    monkeypatch.setattr(
        main.supabase.auth,
        "get_user",
        lambda token: fake_response,
    )

    response = client.get(
        "/protected/profile",
        headers={"Authorization": "Bearer valid-token"},
    )

    assert response.status_code == 200

    body = response.json()

    assert body["user"]["id"] == "user-123"
    assert body["user"]["email"] == "test@example.com"


def test_invalid_token_returns_401(monkeypatch):
    def fail(token):
        raise RuntimeError("invalid token")

    monkeypatch.setattr(
        main.supabase.auth,
        "get_user",
        fail,
    )

    response = client.get(
        "/protected/profile",
        headers={"Authorization": "Bearer tampered-token"},
    )

    assert response.status_code == 401
    assert response.json() == {
        "error": "Invalid or expired token"
    }
