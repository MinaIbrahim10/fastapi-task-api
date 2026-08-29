from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel

from auth_config import auth_config_status, supabase

app = FastAPI(
    title="Task API",
    version="1.1",
    description="A simple in-memory CRUD API for managing tasks."
)


INITIAL_TASKS = [
    {"id": 1, "title": "Learn FastAPI", "done": False},
    {"id": 2, "title": "Build CRUD API", "done": False},
    {"id": 3, "title": "Push project to GitHub", "done": False},
]

tasks = [task.copy() for task in INITIAL_TASKS]


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
    "/auth/health",
    summary="Authentication service health",
    description=(
        "Confirms that the backend loaded its Supabase "
        "configuration without exposing credentials."
    ),
)
def auth_health():
    return {
        "status": "ok",
        **auth_config_status(),
    }


@app.get(
    "/tasks",
    summary="List tasks",
    description=(
        "Returns tasks with optional filtering, search, "
        "and pagination."
    )
)
def get_tasks(
    done: bool | None = None,
    search: str | None = None,
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

    result = tasks

    if done is not None:
        result = [
            task for task in result
            if task["done"] == done
        ]

    if search is not None and search.strip():
        query = search.strip().lower()

        result = [
            task for task in result
            if query in task["title"].lower()
        ]

    result = result[offset:]

    if limit is not None:
        result = result[:limit]

    return result


@app.get(
    "/tasks/{task_id}",
    summary="Get a task by ID",
    description="Returns one task using its ID."
)
def get_task(task_id: int):
    for task in tasks:
        if task["id"] == task_id:
            return task

    return JSONResponse(
        status_code=404,
        content={"error": f"Task {task_id} not found"}
    )


@app.post(
    "/tasks",
    status_code=201,
    summary="Create a new task",
    description="Creates a new task with done set to false."
)
def create_task(task_data: TaskCreate):
    if task_data.title is None or not task_data.title.strip():
        return JSONResponse(
            status_code=400,
            content={"error": "Title is required and cannot be empty"}
        )

    title = task_data.title.strip()

    next_id = max(
        (task["id"] for task in tasks),
        default=0
    ) + 1

    new_task = {
        "id": next_id,
        "title": title,
        "done": False
    }

    tasks.append(new_task)

    return new_task


@app.put(
    "/tasks/{task_id}",
    summary="Update a task",
    description="Updates the title and/or done status of a task."
)
def update_task(task_id: int, task_data: TaskUpdate):
    task = None

    for item in tasks:
        if item["id"] == task_id:
            task = item
            break

    if task is None:
        return JSONResponse(
            status_code=404,
            content={"error": f"Task {task_id} not found"}
        )

    if task_data.title is None and task_data.done is None:
        return JSONResponse(
            status_code=400,
            content={"error": "At least one field is required"}
        )

    if task_data.title is not None:
        if not task_data.title.strip():
            return JSONResponse(
                status_code=400,
                content={"error": "Title cannot be empty"}
            )

        task["title"] = task_data.title.strip()

    if task_data.done is not None:
        task["done"] = task_data.done

    return task


@app.delete(
    "/tasks/{task_id}",
    summary="Delete a task",
    description="Deletes an existing task by ID."
)
def delete_task(task_id: int):
    for index, task in enumerate(tasks):
        if task["id"] == task_id:
            tasks.pop(index)
            return Response(status_code=204)

    return JSONResponse(
        status_code=404,
        content={"error": f"Task {task_id} not found"}
    )


@app.get(
    "/stats",
    summary="Task statistics",
    description="Returns total, completed, and open task counts."
)
def get_stats():
    total = len(tasks)
    completed = sum(1 for task in tasks if task["done"])

    return {
        "total": total,
        "done": completed,
        "open": total - completed
    }


@app.post(
    "/reset",
    summary="Reset tasks",
    description="Restores the original three sample tasks."
)
def reset_tasks():
    tasks.clear()

    tasks.extend(
        task.copy()
        for task in INITIAL_TASKS
    )

    return {
        "message": "Tasks reset",
        "tasks": tasks
    }
