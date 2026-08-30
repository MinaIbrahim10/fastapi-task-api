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


def test_list_tasks_from_postgres():
    response = client.get("/tasks")

    assert response.status_code == 200
    assert len(response.json()) == 3


def test_get_task_from_postgres():
    response = client.get("/tasks/1")

    assert response.status_code == 200
    assert response.json() == {
        "id": 1,
        "title": "Learn FastAPI",
        "done": False,
    }


def test_unknown_task_returns_404():
    response = client.get("/tasks/999")

    assert response.status_code == 404
    assert response.json() == {
        "error": "Task 999 not found"
    }


def test_search_behavior_unchanged():
    response = client.get(
        "/tasks",
        params={"search": "fastapi"},
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["title"] == "Learn FastAPI"


def test_filter_behavior_unchanged():
    response = client.get(
        "/tasks",
        params={"done": False},
    )

    assert response.status_code == 200
    assert len(response.json()) == 3


def test_sort_behavior_unchanged():
    response = client.get(
        "/tasks",
        params={"sort": "title"},
    )

    assert response.status_code == 200

    titles = [
        task["title"]
        for task in response.json()
    ]

    assert titles == sorted(
        titles,
        key=str.lower,
    )


def test_pagination_behavior_unchanged():
    response = client.get(
        "/tasks",
        params={
            "limit": 2,
            "offset": 1,
        },
    )

    assert response.status_code == 200

    assert [
        task["id"]
        for task in response.json()
    ] == [2, 3]


def test_invalid_sort_behavior_unchanged():
    response = client.get(
        "/tasks",
        params={"sort": "random"},
    )

    assert response.status_code == 400
    assert response.json() == {
        "error": "Sort must be 'title'"
    }
