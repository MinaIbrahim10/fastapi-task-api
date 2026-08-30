from fastapi import FastAPI, Request
from datetime import datetime, timezone
from fastapi.responses import JSONResponse, Response
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel
from redis_client import redis_ping
from postgres_repository import (
    initialize_database,
    list_tasks as repository_list_tasks,
    get_task_by_id as repository_get_task_by_id,
    create_task as repository_create_task,
    update_task as repository_update_task,
    delete_task as repository_delete_task,
    get_stats as repository_get_stats,
    reset_tasks as repository_reset_tasks,
    database_health,
)


initialize_database()


app = FastAPI(
    title="Task API",
    version="1.1",
    description="A PostgreSQL-backed CRUD API for managing tasks."
)


@app.on_event("startup")
def verify_redis_connection():
    if not redis_ping():
        raise RuntimeError(
            "Redis PING failed during startup"
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
    try:
        if database_health():
            return {
                "status": "ok",
                "db": "ok",
            }
    except Exception:
        pass

    return JSONResponse(
        status_code=503,
        content={
            "status": "error",
            "db": "unavailable",
        },
    )


@app.get(
    "/tasks",
    summary="List tasks",
    description=(
        "Returns tasks from PostgreSQL with optional filtering, search, "
        "sorting, and pagination."
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

    try:
        return repository_list_tasks(
            done=done,
            search=search,
            sort=sort,
            limit=limit,
            offset=offset,
        )

    except ValueError as exc:
        return JSONResponse(
            status_code=400,
            content={"error": str(exc)}
        )


@app.get(
    "/tasks/{task_id}",
    summary="Get a task by ID",
    description="Returns one task from PostgreSQL using its ID."
)
def get_task(task_id: int):
    task = repository_get_task_by_id(
        task_id
    )

    if task is None:
        return JSONResponse(
            status_code=404,
            content={"error": f"Task {task_id} not found"}
        )

    return task


@app.post(
    "/tasks",
    status_code=201,
    summary="Create a new task",
    description="Creates a new task in PostgreSQL with done set to false."
)
def create_task(task_data: TaskCreate):
    if task_data.title is None or not task_data.title.strip():
        return JSONResponse(
            status_code=400,
            content={"error": "Title is required and cannot be empty"}
        )

    return repository_create_task(
        task_data.title.strip()
    )


@app.put(
    "/tasks/{task_id}",
    summary="Update a task",
    description="Updates an existing task in PostgreSQL."
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

    title = (
        task_data.title.strip()
        if task_data.title is not None
        else None
    )

    task = repository_update_task(
        task_id=task_id,
        title=title,
        done=task_data.done,
    )

    if task is None:
        return JSONResponse(
            status_code=404,
            content={"error": f"Task {task_id} not found"}
        )

    return task


@app.delete(
    "/tasks/{task_id}",
    summary="Delete a task",
    description="Deletes an existing task from PostgreSQL."
)
def delete_task(task_id: int):
    deleted = repository_delete_task(
        task_id
    )

    if not deleted:
        return JSONResponse(
            status_code=404,
            content={"error": f"Task {task_id} not found"}
        )

    return Response(status_code=204)


@app.get(
    "/stats",
    summary="Task statistics",
    description="Returns task counts calculated directly by PostgreSQL."
)
def get_stats():
    return repository_get_stats()


@app.post(
    "/reset",
    summary="Reset tasks",
    description="Resets PostgreSQL to the original three sample tasks."
)
def reset_tasks():
    tasks = repository_reset_tasks()

    return {
        "message": "Tasks reset",
        "tasks": tasks,
    }
