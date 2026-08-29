from types import SimpleNamespace

from fastapi.testclient import TestClient

import main


client = TestClient(main.app)


def make_user(role=None):
    metadata = {}

    if role is not None:
        metadata["role"] = role

    return SimpleNamespace(
        id="user-123",
        email="test@example.com",
        created_at="2026-08-30T00:00:00+00:00",
        app_metadata=metadata,
    )


def mock_valid_user(monkeypatch, role=None):
    response = SimpleNamespace(
        user=make_user(role=role)
    )

    monkeypatch.setattr(
        main.supabase.auth,
        "get_user",
        lambda token: response,
    )


def test_dashboard_uses_reusable_auth(monkeypatch):
    mock_valid_user(monkeypatch)

    response = client.get(
        "/protected/dashboard",
        headers={"Authorization": "Bearer valid-token"},
    )

    assert response.status_code == 200


def test_dashboard_rejects_invalid_token(monkeypatch):
    def fail(token):
        raise RuntimeError("invalid")

    monkeypatch.setattr(
        main.supabase.auth,
        "get_user",
        fail,
    )

    response = client.get(
        "/protected/dashboard",
        headers={"Authorization": "Bearer bad-token"},
    )

    assert response.status_code == 401


def test_non_admin_gets_403(monkeypatch):
    mock_valid_user(monkeypatch, role="user")

    response = client.get(
        "/protected/admin",
        headers={"Authorization": "Bearer valid-token"},
    )

    assert response.status_code == 403
    assert response.json() == {
        "error": "Admin access required"
    }


def test_admin_is_allowed(monkeypatch):
    mock_valid_user(monkeypatch, role="admin")

    response = client.get(
        "/protected/admin",
        headers={"Authorization": "Bearer valid-token"},
    )

    assert response.status_code == 200


def test_logout_success(monkeypatch):
    mock_valid_user(monkeypatch)

    monkeypatch.setattr(
        main.supabase.auth,
        "sign_out",
        lambda: None,
    )

    response = client.post(
        "/auth/logout",
        headers={"Authorization": "Bearer valid-token"},
    )

    assert response.status_code == 204
    assert response.content == b""


def test_refresh_success(monkeypatch):
    session = SimpleNamespace(
        access_token="new-access",
        refresh_token="new-refresh",
        expires_in=3600,
    )

    response_obj = SimpleNamespace(
        session=session,
    )

    monkeypatch.setattr(
        main.supabase.auth,
        "refresh_session",
        lambda refresh_token: response_obj,
    )

    response = client.post(
        "/auth/refresh",
        json={"refresh_token": "old-refresh"},
    )

    assert response.status_code == 200
    assert response.json()["access_token"] == "new-access"


def test_missing_refresh_token_returns_400():
    response = client.post(
        "/auth/refresh",
        json={},
    )

    assert response.status_code == 400


def test_invalid_refresh_token_returns_401(monkeypatch):
    def fail(refresh_token):
        raise RuntimeError("invalid")

    monkeypatch.setattr(
        main.supabase.auth,
        "refresh_session",
        fail,
    )

    response = client.post(
        "/auth/refresh",
        json={"refresh_token": "bad"},
    )

    assert response.status_code == 401


def test_login_rate_limit_returns_429(monkeypatch):
    main._failed_login_attempts.clear()

    def fail(credentials):
        raise RuntimeError("invalid")

    monkeypatch.setattr(
        main.supabase.auth,
        "sign_in_with_password",
        fail,
    )

    body = {
        "email": "rate@example.com",
        "password": "password123",
    }

    for _ in range(main.LOGIN_RATE_LIMIT_MAX_FAILURES):
        response = client.post(
            "/auth/login",
            json=body,
        )
        assert response.status_code == 401

    response = client.post(
        "/auth/login",
        json=body,
    )

    assert response.status_code == 429
