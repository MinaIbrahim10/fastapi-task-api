from contextlib import asynccontextmanager
import os

from fastapi import FastAPI, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
import redis

import database
from models import Task, TaskCreate, TaskUpdate


@asynccontextmanager
async def lifespan(app: FastAPI):
    database.initialize_database()
    redis_client = redis.Redis.from_url(
        os.getenv("REDIS_URL", "redis://redis:6379/0")
    )
    redis_client.ping()
    app.state.redis = redis_client
    try:
        yield
    finally:
        redis_client.close()


app = FastAPI(
    title="Task API",
    version="1.1",
    description="A FastAPI application for managing tasks.",
    lifespan=lifespan,
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
):
    return JSONResponse(
        status_code=400,
        content={"error": "Invalid request body or parameters"},
    )


def not_found(task_id: int) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"error": f"Task {task_id} not found"},
    )


@app.get("/tasks", response_model=list[Task])
def list_tasks():
    return database.list_tasks()


@app.get("/tasks/{task_id}", response_model=Task)
def get_task(task_id: int):
    task = database.get_task(task_id)
    if task is None:
        return not_found(task_id)
    return task


@app.post("/tasks", response_model=Task, status_code=status.HTTP_201_CREATED)
def create_task(task: TaskCreate):
    if task.title is None or not task.title.strip():
        return JSONResponse(
            status_code=400,
            content={"error": "Title is required and cannot be empty"},
        )
    return database.create_task(task.title.strip())


@app.put("/tasks/{task_id}", response_model=Task)
def update_task(task_id: int, task: TaskUpdate):
    if database.get_task(task_id) is None:
        return not_found(task_id)

    changes = task.model_dump(exclude_unset=True)
    if not changes or all(value is None for value in changes.values()):
        return JSONResponse(
            status_code=400,
            content={"error": "At least one field is required"},
        )
    if task.title is not None:
        if not task.title.strip():
            return JSONResponse(
                status_code=400,
                content={"error": "Title cannot be empty"},
            )
        changes["title"] = task.title.strip()

    updated_task = database.update_task(task_id, changes)
    if updated_task is None:
        return not_found(task_id)
    return updated_task


@app.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: int):
    if not database.delete_task(task_id):
        return not_found(task_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/health")
def health():
    database.check_health()
    return {"status": "ok"}
