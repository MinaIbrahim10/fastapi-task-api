import os
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv


load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

SCHEMA_PATH = (
    Path(__file__).resolve().parent
    / "sql"
    / "001_create_tasks.sql"
)

SEED_TASKS = [
    (1, "Learn FastAPI", False),
    (2, "Build CRUD API", False),
    (3, "Push project to GitHub", False),
]


def validate_database_config() -> str:
    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL is required"
        )

    if not DATABASE_URL.startswith(
        ("postgresql://", "postgres://")
    ):
        raise RuntimeError(
            "DATABASE_URL must be a PostgreSQL connection string"
        )

    return DATABASE_URL


def get_connection():
    """
    Return a PostgreSQL connection using dictionary-like rows.
    """
    url = validate_database_config()

    return psycopg.connect(
        url,
        row_factory=dict_row,
    )


def create_schema() -> None:
    """
    Create the tasks table from the committed SQL schema.
    """
    schema_sql = SCHEMA_PATH.read_text()

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(schema_sql)

        conn.commit()


def seed_tasks_once() -> bool:
    """
    Seed the three original tasks only when the table is empty.

    Returns True only when seeding occurred.
    """
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) AS count FROM tasks"
            )

            count = cursor.fetchone()["count"]

            if count != 0:
                return False

            cursor.executemany(
                """
                INSERT INTO tasks (
                    id,
                    title,
                    done
                )
                VALUES (%s, %s, %s)
                """,
                SEED_TASKS,
            )

            # BIGSERIAL sequence must advance beyond explicit seed IDs.
            cursor.execute(
                """
                SELECT setval(
                    pg_get_serial_sequence('tasks', 'id'),
                    (SELECT MAX(id) FROM tasks),
                    true
                )
                """
            )

        conn.commit()

    return True


def initialize_database() -> bool:
    """
    Create schema and perform seed-once initialization.
    """
    create_schema()
    return seed_tasks_once()


def database_health() -> bool:
    """
    Execute a real database round trip.
    """
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1 AS ok")
            row = cursor.fetchone()

    return row["ok"] == 1


if __name__ == "__main__":
    seeded = initialize_database()

    print("Database initialized.")
    print("Seed inserted:", seeded)
    print("Database health:", database_health())


def list_tasks(
    done: bool | None = None,
    search: str | None = None,
    sort: str | None = None,
    limit: int | None = None,
    offset: int = 0,
):
    query = """
        SELECT id, title, done
        FROM tasks
        WHERE TRUE
    """

    params = []

    if done is not None:
        query += " AND done = %s"
        params.append(done)

    if search is not None and search.strip():
        query += " AND LOWER(title) LIKE %s"
        params.append(
            f"%{search.strip().lower()}%"
        )

    if sort is None:
        query += " ORDER BY id"

    elif sort == "title":
        query += " ORDER BY LOWER(title), id"

    else:
        raise ValueError(
            "Sort must be 'title'"
        )

    if limit is not None:
        query += " LIMIT %s OFFSET %s"
        params.extend([
            limit,
            offset,
        ])

    elif offset > 0:
        query += " OFFSET %s"
        params.append(offset)

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                query,
                params,
            )

            rows = cursor.fetchall()

    return [
        {
            "id": row["id"],
            "title": row["title"],
            "done": bool(row["done"]),
        }
        for row in rows
    ]


def get_task_by_id(task_id: int):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, title, done
                FROM tasks
                WHERE id = %s
                """,
                (task_id,),
            )

            row = cursor.fetchone()

    if row is None:
        return None

    return {
        "id": row["id"],
        "title": row["title"],
        "done": bool(row["done"]),
    }


def create_task(title: str):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO tasks (
                    title,
                    done,
                    created_at,
                    updated_at
                )
                VALUES (%s, FALSE, NOW(), NOW())
                RETURNING id, title, done
                """,
                (title,),
            )

            row = cursor.fetchone()

        conn.commit()

    return {
        "id": row["id"],
        "title": row["title"],
        "done": bool(row["done"]),
    }


def update_task(
    task_id: int,
    title: str | None = None,
    done: bool | None = None,
):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, title, done
                FROM tasks
                WHERE id = %s
                """,
                (task_id,),
            )

            existing = cursor.fetchone()

            if existing is None:
                return None

            new_title = (
                title
                if title is not None
                else existing["title"]
            )

            new_done = (
                done
                if done is not None
                else existing["done"]
            )

            cursor.execute(
                """
                UPDATE tasks
                SET
                    title = %s,
                    done = %s,
                    updated_at = NOW()
                WHERE id = %s
                RETURNING id, title, done
                """,
                (
                    new_title,
                    new_done,
                    task_id,
                ),
            )

            row = cursor.fetchone()

        conn.commit()

    return {
        "id": row["id"],
        "title": row["title"],
        "done": bool(row["done"]),
    }


def delete_task(task_id: int) -> bool:
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM tasks
                WHERE id = %s
                RETURNING id
                """,
                (task_id,),
            )

            deleted = cursor.fetchone()

        conn.commit()

    return deleted is not None


def get_stats():
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    COUNT(*) AS total,
                    COUNT(*) FILTER (
                        WHERE done = TRUE
                    ) AS completed
                FROM tasks
                """
            )

            row = cursor.fetchone()

    total = row["total"]
    completed = row["completed"]

    return {
        "total": total,
        "done": completed,
        "open": total - completed,
    }


def reset_tasks():
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "TRUNCATE TABLE tasks RESTART IDENTITY"
            )

            cursor.executemany(
                """
                INSERT INTO tasks (
                    id,
                    title,
                    done
                )
                VALUES (%s, %s, %s)
                """,
                SEED_TASKS,
            )

            cursor.execute(
                """
                SELECT setval(
                    pg_get_serial_sequence('tasks', 'id'),
                    (SELECT MAX(id) FROM tasks),
                    true
                )
                """
            )

            cursor.execute(
                """
                SELECT id, title, done
                FROM tasks
                ORDER BY id
                """
            )

            rows = cursor.fetchall()

        conn.commit()

    return [
        {
            "id": row["id"],
            "title": row["title"],
            "done": bool(row["done"]),
        }
        for row in rows
    ]
