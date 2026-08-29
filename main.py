from fastapi import FastAPI, Request
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from fastapi.responses import JSONResponse, Response
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel


DB_PATH = Path("tasks.db")


def get_db():
    """Open a SQLite connection with dictionary-like rows."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def initialize_database():
    """Create the tasks table and seed it once when empty."""
    with get_db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                done INTEGER NOT NULL DEFAULT 0 CHECK(done IN (0, 1)),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        # Indexes support common search/filter access patterns.
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_tasks_title ON tasks(title)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_tasks_done ON tasks(done)"
        )

        count = conn.execute(
            "SELECT COUNT(*) AS count FROM tasks"
        ).fetchone()["count"]

        if count == 0:
            now = utc_now()

            try:
                conn.execute("BEGIN")

                conn.executemany(
                    """
                    INSERT INTO tasks (
                        id,
                        title,
                        done,
                        created_at,
                        updated_at
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    [
                        (1, "Learn FastAPI", 0, now, now),
                        (2, "Build CRUD API", 0, now, now),
                        (3, "Push project to GitHub", 0, now, now),
                    ],
                )

                conn.commit()
            except Exception:
                conn.rollback()
                raise


initialize_database()

app = FastAPI(
    title="Task API",
    version="1.1",
    description="A simple in-memory CRUD API for managing tasks."
)


class TaskCreate(BaseModel):
    title: str | None = None


class TaskUpdate(BaseModel):
    title: str | None = None
    done: bool | None = None


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError
):
    return JSONResponse(
        status_code=400,
        content={"error": "Invalid request body or parameters"}
    )


@app.get(
    "/",
    summary="API information",
    description="Returns basic information about the Task API."
)
def root():
    return {
        "name": "Task API",
        "version": "1.1",
        "endpoints": [
            "/tasks",
            "/stats",
            "/reset",
            "/health"
        ]
    }


@app.get(
    "/health",
    summary="Health check",
    description="Checks whether the API server is running."
)
def health():
    return {"status": "ok"}


@app.get(
    "/tasks",
    summary="List tasks",
    description=(
        "Returns tasks from SQLite with optional filtering, search, "
        "and pagination."
    )
)
def get_tasks(
    done: bool | None = None,
    search: str | None = None,
    sort: str | None = None,
    limit: int | None = None,
    offset: int = 0
):
    if offset < 0:
        return JSONResponse(
            status_code=400,
            content={"error": "Offset cannot be negative"}
        )

    if limit is not None and limit <= 0:
        return JSONResponse(
            status_code=400,
            content={"error": "Limit must be greater than zero"}
        )

    query = """
        SELECT id, title, done
        FROM tasks
        WHERE 1 = 1
    """
    params = []

    if done is not None:
        query += " AND done = ?"
        params.append(1 if done else 0)

    if search is not None and search.strip():
        query += " AND LOWER(title) LIKE ?"
        params.append(f"%{search.strip().lower()}%")

    if sort is None:
        query += " ORDER BY id"
    elif sort == "title":
        query += " ORDER BY title COLLATE NOCASE, id"
    else:
        return JSONResponse(
            status_code=400,
            content={"error": "Sort must be 'title'"}
        )

    if limit is not None:
        query += " LIMIT ? OFFSET ?"
        params.extend([limit, offset])
    elif offset > 0:
        query += " LIMIT -1 OFFSET ?"
        params.append(offset)

    with get_db() as conn:
        rows = conn.execute(query, params).fetchall()

    return [
        {
            "id": row["id"],
            "title": row["title"],
            "done": bool(row["done"]),
        }
        for row in rows
    ]


@app.get(
    "/tasks/{task_id}",
    summary="Get a task by ID",
    description="Returns one task from SQLite using its ID."
)
def get_task(task_id: int):
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT id, title, done
            FROM tasks
            WHERE id = ?
            """,
            (task_id,),
        ).fetchone()

    if row is None:
        return JSONResponse(
            status_code=404,
            content={"error": f"Task {task_id} not found"}
        )

    return {
        "id": row["id"],
        "title": row["title"],
        "done": bool(row["done"]),
    }


@app.post(
    "/tasks",
    status_code=201,
    summary="Create a new task",
    description="Creates a new task in SQLite with done set to false."
)
def create_task(task_data: TaskCreate):
    if task_data.title is None or not task_data.title.strip():
        return JSONResponse(
            status_code=400,
            content={"error": "Title is required and cannot be empty"}
        )

    title = task_data.title.strip()
    now = utc_now()

    with get_db() as conn:
        cursor = conn.execute(
            """
            INSERT INTO tasks (
                title,
                done,
                created_at,
                updated_at
            )
            VALUES (?, 0, ?, ?)
            """,
            (title, now, now),
        )

        task_id = cursor.lastrowid

        row = conn.execute(
            """
            SELECT id, title, done
            FROM tasks
            WHERE id = ?
            """,
            (task_id,),
        ).fetchone()

        conn.commit()

    return {
        "id": row["id"],
        "title": row["title"],
        "done": bool(row["done"]),
    }


@app.put(
    "/tasks/{task_id}",
    summary="Update a task",
    description="Updates an existing task in SQLite."
)
def update_task(task_id: int, task_data: TaskUpdate):
    if task_data.title is None and task_data.done is None:
        return JSONResponse(
            status_code=400,
            content={"error": "At least one field is required"}
        )

    if task_data.title is not None and not task_data.title.strip():
        return JSONResponse(
            status_code=400,
            content={"error": "Title cannot be empty"}
        )

    with get_db() as conn:
        existing = conn.execute(
            """
            SELECT id, title, done
            FROM tasks
            WHERE id = ?
            """,
            (task_id,),
        ).fetchone()

        if existing is None:
            return JSONResponse(
                status_code=404,
                content={"error": f"Task {task_id} not found"}
            )

        new_title = (
            task_data.title.strip()
            if task_data.title is not None
            else existing["title"]
        )

        new_done = (
            1 if task_data.done
            else 0 if task_data.done is not None
            else existing["done"]
        )

        now = utc_now()

        conn.execute(
            """
            UPDATE tasks
            SET title = ?, done = ?, updated_at = ?
            WHERE id = ?
            """,
            (new_title, new_done, now, task_id),
        )

        row = conn.execute(
            """
            SELECT id, title, done
            FROM tasks
            WHERE id = ?
            """,
            (task_id,),
        ).fetchone()

        conn.commit()

    return {
        "id": row["id"],
        "title": row["title"],
        "done": bool(row["done"]),
    }


@app.delete(
    "/tasks/{task_id}",
    summary="Delete a task",
    description="Deletes an existing task from SQLite."
)
def delete_task(task_id: int):
    with get_db() as conn:
        existing = conn.execute(
            "SELECT id FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()

        if existing is None:
            return JSONResponse(
                status_code=404,
                content={"error": f"Task {task_id} not found"}
            )

        conn.execute(
            "DELETE FROM tasks WHERE id = ?",
            (task_id,),
        )

        conn.commit()

    return Response(status_code=204)


@app.get(
    "/stats",
    summary="Task statistics",
    description="Returns task counts calculated directly by SQLite."
)
def get_stats():
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN done = 1 THEN 1 ELSE 0 END) AS completed
            FROM tasks
            """
        ).fetchone()

    total = row["total"]
    completed = row["completed"] or 0

    return {
        "total": total,
        "done": completed,
        "open": total - completed
    }


@app.post(
    "/reset",
    summary="Reset tasks",
    description="Resets the SQLite database to the original three sample tasks."
)
def reset_tasks():
    now = utc_now()

    with get_db() as conn:
        conn.execute("DELETE FROM tasks")

        conn.executemany(
            """
            INSERT INTO tasks (
                id,
                title,
                done,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (1, "Learn FastAPI", 0, now, now),
                (2, "Build CRUD API", 0, now, now),
                (3, "Push project to GitHub", 0, now, now),
            ],
        )

        conn.commit()

        rows = conn.execute(
            """
            SELECT id, title, done
            FROM tasks
            ORDER BY id
            """
        ).fetchall()

    tasks = [
        {
            "id": row["id"],
            "title": row["title"],
            "done": bool(row["done"]),
        }
        for row in rows
    ]

    return {
        "message": "Tasks reset",
        "tasks": tasks
    }

