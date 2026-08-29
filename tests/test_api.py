import sqlite3

import pytest
from fastapi.testclient import TestClient

import main


client = TestClient(main.app)


@pytest.fixture(autouse=True)
def isolated_database(tmp_path, monkeypatch):
    test_db = tmp_path / "test_tasks.db"
    monkeypatch.setattr(main, "DB_PATH", test_db)

    main.initialize_database()
    yield test_db


def test_database_seeds_exactly_once():
    main.initialize_database()

    with main.get_db() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM tasks"
        ).fetchone()[0]

    assert count == 3


def test_list_tasks_reads_from_database():
    response = client.get("/tasks")

    assert response.status_code == 200
    assert len(response.json()) == 3


def test_get_unknown_task_returns_404():
    response = client.get("/tasks/999")

    assert response.status_code == 404
    assert response.json() == {
        "error": "Task 999 not found"
    }


def test_create_task_persists_to_database():
    response = client.post(
        "/tasks",
        json={"title": "Database test"},
    )

    assert response.status_code == 201

    task = response.json()

    with main.get_db() as conn:
        row = conn.execute(
            "SELECT title, done FROM tasks WHERE id = ?",
            (task["id"],),
        ).fetchone()

    assert row is not None
    assert row["title"] == "Database test"
    assert row["done"] == 0


def test_missing_title_returns_400():
    response = client.post("/tasks", json={})

    assert response.status_code == 400


def test_update_task_uses_database():
    response = client.put(
        "/tasks/1",
        json={
            "title": "Updated with SQL",
            "done": True,
        },
    )

    assert response.status_code == 200
    assert response.json()["title"] == "Updated with SQL"
    assert response.json()["done"] is True

    with main.get_db() as conn:
        row = conn.execute(
            "SELECT title, done FROM tasks WHERE id = 1"
        ).fetchone()

    assert row["title"] == "Updated with SQL"
    assert row["done"] == 1


def test_delete_task_removes_database_row():
    response = client.delete("/tasks/1")

    assert response.status_code == 204

    with main.get_db() as conn:
        row = conn.execute(
            "SELECT id FROM tasks WHERE id = 1"
        ).fetchone()

    assert row is None


def test_search_is_sql_backed():
    response = client.get(
        "/tasks",
        params={"search": "fastapi"},
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["title"] == "Learn FastAPI"


def test_done_filter():
    client.put(
        "/tasks/1",
        json={"done": True},
    )

    response = client.get(
        "/tasks",
        params={"done": True},
    )

    assert response.status_code == 200

    tasks = response.json()

    assert len(tasks) == 1
    assert tasks[0]["done"] is True


def test_pagination():
    response = client.get(
        "/tasks",
        params={
            "limit": 2,
            "offset": 1,
        },
    )

    assert response.status_code == 200
    assert [task["id"] for task in response.json()] == [2, 3]


def test_stats_uses_database_counts():
    client.put(
        "/tasks/1",
        json={"done": True},
    )

    response = client.get("/stats")

    assert response.status_code == 200
    assert response.json() == {
        "total": 3,
        "done": 1,
        "open": 2,
    }


def test_reset_restores_seed_tasks():
    client.delete("/tasks/1")

    response = client.post("/reset")

    assert response.status_code == 200
    assert len(response.json()["tasks"]) == 3

    with main.get_db() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM tasks"
        ).fetchone()[0]

    assert count == 3
