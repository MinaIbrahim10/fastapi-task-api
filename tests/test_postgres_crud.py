from fastapi.testclient import TestClient

import main
from postgres_repository import (
    get_connection,
    initialize_database,
)


client = TestClient(main.app)


def reset_database():
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "TRUNCATE TABLE tasks RESTART IDENTITY"
            )

        conn.commit()

    initialize_database()


def setup_function():
    reset_database()


def test_create_task():
    response = client.post(
        "/tasks",
        json={"title": "Postgres create"},
    )

    assert response.status_code == 201
    assert response.json()["title"] == "Postgres create"
    assert response.json()["done"] is False


def test_create_missing_title_is_400():
    response = client.post(
        "/tasks",
        json={},
    )

    assert response.status_code == 400


def test_update_task():
    response = client.put(
        "/tasks/1",
        json={
            "title": "Updated",
            "done": True,
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "id": 1,
        "title": "Updated",
        "done": True,
    }


def test_update_unknown_is_404():
    response = client.put(
        "/tasks/99999",
        json={"done": True},
    )

    assert response.status_code == 404


def test_delete_task():
    response = client.delete(
        "/tasks/1"
    )

    assert response.status_code == 204

    response = client.get(
        "/tasks/1"
    )

    assert response.status_code == 404


def test_delete_unknown_is_404():
    response = client.delete(
        "/tasks/99999"
    )

    assert response.status_code == 404


def test_stats_use_postgres():
    client.put(
        "/tasks/1",
        json={"done": True},
    )

    response = client.get(
        "/stats"
    )

    assert response.status_code == 200

    assert response.json() == {
        "total": 3,
        "done": 1,
        "open": 2,
    }


def test_reset_restores_seed_tasks():
    client.delete(
        "/tasks/1"
    )

    response = client.post(
        "/reset"
    )

    assert response.status_code == 200
    assert len(
        response.json()["tasks"]
    ) == 3


def test_health_checks_database():
    response = client.get(
        "/health"
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "db": "ok",
    }
