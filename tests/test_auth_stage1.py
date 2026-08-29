from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import main


client = TestClient(main.app)


def fake_user():
    return SimpleNamespace(
        id="user-123",
        email="test@example.com",
        created_at="2026-08-30T00:00:00+00:00",
    )


def test_signup_success(monkeypatch):
    fake_response = SimpleNamespace(
        user=fake_user(),
        session=SimpleNamespace(),
    )

    monkeypatch.setattr(
        main.supabase.auth,
        "sign_up",
        lambda credentials: fake_response,
    )

    response = client.post(
        "/auth/signup",
        json={
            "email": "Test@Example.com",
            "password": "password123",
        },
    )

    assert response.status_code == 201
    body = response.json()

    assert body["user"]["id"] == "user-123"
    assert body["user"]["email"] == "test@example.com"
    assert body["email_confirmation_required"] is False


def test_signup_invalid_email_returns_400():
    response = client.post(
        "/auth/signup",
        json={
            "email": "not-an-email",
            "password": "password123",
        },
    )

    assert response.status_code == 400


def test_signup_short_password_returns_400():
    response = client.post(
        "/auth/signup",
        json={
            "email": "test@example.com",
            "password": "short",
        },
    )

    assert response.status_code == 400


def test_login_success(monkeypatch):
    fake_session = SimpleNamespace(
        access_token="access-token-value",
        refresh_token="refresh-token-value",
        expires_in=3600,
    )

    fake_response = SimpleNamespace(
        user=fake_user(),
        session=fake_session,
    )

    monkeypatch.setattr(
        main.supabase.auth,
        "sign_in_with_password",
        lambda credentials: fake_response,
    )

    response = client.post(
        "/auth/login",
        json={
            "email": "test@example.com",
            "password": "password123",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["access_token"] == "access-token-value"
    assert body["refresh_token"] == "refresh-token-value"
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 3600


def test_login_wrong_credentials_returns_401(monkeypatch):
    def fail_login(credentials):
        raise RuntimeError("Invalid login credentials")

    monkeypatch.setattr(
        main.supabase.auth,
        "sign_in_with_password",
        fail_login,
    )

    response = client.post(
        "/auth/login",
        json={
            "email": "test@example.com",
            "password": "wrongpassword",
        },
    )

    assert response.status_code == 401
    assert response.json() == {
        "error": "Invalid login credentials"
    }


def test_missing_auth_fields_return_400():
    response = client.post(
        "/auth/login",
        json={},
    )

    assert response.status_code == 400
