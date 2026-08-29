from fastapi.testclient import TestClient

import main


client = TestClient(main.app)


def test_docs_is_available():
    response = client.get("/docs")

    assert response.status_code == 200
    assert "Swagger UI" in response.text


def test_openapi_contains_bearer_security_scheme():
    response = client.get("/openapi.json")

    assert response.status_code == 200

    schema = response.json()

    schemes = (
        schema
        .get("components", {})
        .get("securitySchemes", {})
    )

    assert "SupabaseJWT" in schemes

    bearer = schemes["SupabaseJWT"]

    assert bearer["type"] == "http"
    assert bearer["scheme"] == "bearer"


def test_profile_is_marked_as_protected_in_openapi():
    schema = client.get("/openapi.json").json()

    operation = schema["paths"]["/protected/profile"]["get"]

    assert operation.get("security") == [
        {"SupabaseJWT": []}
    ]


def test_dashboard_is_marked_as_protected_in_openapi():
    schema = client.get("/openapi.json").json()

    operation = schema["paths"]["/protected/dashboard"]["get"]

    assert operation.get("security") == [
        {"SupabaseJWT": []}
    ]


def test_admin_is_marked_as_protected_in_openapi():
    schema = client.get("/openapi.json").json()

    operation = schema["paths"]["/protected/admin"]["get"]

    assert operation.get("security") == [
        {"SupabaseJWT": []}
    ]


def test_logout_is_marked_as_protected_in_openapi():
    schema = client.get("/openapi.json").json()

    operation = schema["paths"]["/auth/logout"]["post"]

    assert operation.get("security") == [
        {"SupabaseJWT": []}
    ]


def test_public_route_has_no_security_requirement():
    schema = client.get("/openapi.json").json()

    operation = schema["paths"]["/public/info"]["get"]

    assert not operation.get("security")


def test_login_has_no_security_requirement():
    schema = client.get("/openapi.json").json()

    operation = schema["paths"]["/auth/login"]["post"]

    assert not operation.get("security")


def test_signup_has_no_security_requirement():
    schema = client.get("/openapi.json").json()

    operation = schema["paths"]["/auth/signup"]["post"]

    assert not operation.get("security")
