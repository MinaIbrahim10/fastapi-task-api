import sqlite3
from pathlib import Path

from fastapi import FastAPI, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel


app = FastAPI(
    title="Task API",
    version="1.1",
    description="A FastAPI application for managing tasks.",
)

DATABASE_PATH = Path(__file__).with_name("tasks.db")
INITIAL_TASKS = [
    (1, "Learn FastAPI", 0),
    (2, "Build CRUD API", 0),
    (3, "Push project to GitHub", 0),
]


class TaskCreate(BaseModel):
    title: str | None = None


class TaskUpdate(BaseModel):
    title: str | None = None
    done: bool | None = None


def get_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def task_to_dict(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "title": row["title"],
        "done": bool(row["done"]),
    }


def initialize_database() -> None:
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY,
                title TEXT NOT NULL,
                done INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        task_count = connection.execute(
            "SELECT COUNT(*) FROM tasks"
        ).fetchone()[0]
        if task_count == 0:
            connection.executemany(
                "INSERT INTO tasks (id, title, done) VALUES (?, ?, ?)",
                INITIAL_TASKS,
            )


initialize_database()


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
):
    return JSONResponse(
        status_code=400,
        content={"error": "Invalid request body or parameters"},
    )


@app.get("/tasks")
def list_tasks():
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT id, title, done FROM tasks ORDER BY id"
        ).fetchall()
    return [task_to_dict(row) for row in rows]


@app.get("/tasks/{task_id}")
def get_task(task_id: int):
    with get_connection() as connection:
        row = connection.execute(
            "SELECT id, title, done FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()
    if row is None:
        return JSONResponse(
            status_code=404,
            content={"error": f"Task {task_id} not found"},
        )
    return task_to_dict(row)


@app.post("/tasks", status_code=status.HTTP_201_CREATED)
def create_task(task_data: TaskCreate):
    if task_data.title is None or not task_data.title.strip():
        return JSONResponse(
            status_code=400,
            content={"error": "Title is required and cannot be empty"},
        )

    title = task_data.title.strip()
    with get_connection() as connection:
        cursor = connection.execute(
            "INSERT INTO tasks (title, done) VALUES (?, ?)",
            (title, 0),
        )
        row = connection.execute(
            "SELECT id, title, done FROM tasks WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
    return task_to_dict(row)


@app.put("/tasks/{task_id}")
def update_task(task_id: int, task_data: TaskUpdate):
    with get_connection() as connection:
        existing = connection.execute(
            "SELECT id, title, done FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()
        if existing is None:
            return JSONResponse(
                status_code=404,
                content={"error": f"Task {task_id} not found"},
            )
        if task_data.title is None and task_data.done is None:
            return JSONResponse(
                status_code=400,
                content={"error": "At least one field is required"},
            )
        if task_data.title is not None and not task_data.title.strip():
            return JSONResponse(
                status_code=400,
                content={"error": "Title cannot be empty"},
            )

        title = (
            task_data.title.strip()
            if task_data.title is not None
            else existing["title"]
        )
        done = (
            int(task_data.done)
            if task_data.done is not None
            else existing["done"]
        )
        connection.execute(
            "UPDATE tasks SET title = ?, done = ? WHERE id = ?",
            (title, done, task_id),
        )
        row = connection.execute(
            "SELECT id, title, done FROM tasks WHERE id = ?",
            (task_id,),
        ).fetchone()
    return task_to_dict(row)


@app.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: int):
    with get_connection() as connection:
        cursor = connection.execute(
            "DELETE FROM tasks WHERE id = ?",
            (task_id,),
        )
    if cursor.rowcount == 0:
        return JSONResponse(
            status_code=404,
            content={"error": f"Task {task_id} not found"},
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
