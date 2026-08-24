from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel


app = FastAPI(
    title="Task API",
    version="1.1",
    description="An in-memory Task CRUD API."
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
async def validation_error(
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
    description="Returns information about the Task API."
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
    description="Checks whether the API is running."
)
def health():
    return {"status": "ok"}


@app.get(
    "/tasks",
    summary="List tasks",
    description="Lists tasks with optional filtering, search, and pagination."
)
def list_tasks(
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
    summary="Get task",
    description="Returns one task by ID."
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
    summary="Create task",
    description="Creates a new task."
)
def create_task(data: TaskCreate):
    if data.title is None or not data.title.strip():
        return JSONResponse(
            status_code=400,
            content={"error": "Title is required and cannot be empty"}
        )

    task = {
        "id": max(
            (task["id"] for task in tasks),
            default=0
        ) + 1,
        "title": data.title.strip(),
        "done": False
    }

    tasks.append(task)

    return task


@app.put(
    "/tasks/{task_id}",
    summary="Update task",
    description="Updates the title and/or done state of a task."
)
def update_task(task_id: int, data: TaskUpdate):
    task = next(
        (task for task in tasks if task["id"] == task_id),
        None
    )

    if task is None:
        return JSONResponse(
            status_code=404,
            content={"error": f"Task {task_id} not found"}
        )

    if data.title is None and data.done is None:
        return JSONResponse(
            status_code=400,
            content={"error": "At least one field is required"}
        )

    if data.title is not None:
        if not data.title.strip():
            return JSONResponse(
                status_code=400,
                content={"error": "Title cannot be empty"}
            )

        task["title"] = data.title.strip()

    if data.done is not None:
        task["done"] = data.done

    return task


@app.delete(
    "/tasks/{task_id}",
    status_code=204,
    summary="Delete task",
    description="Deletes a task by ID."
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
    description="Returns total, done, and open task counts."
)
def stats():
    total = len(tasks)
    done = sum(
        1 for task in tasks
        if task["done"]
    )

    return {
        "total": total,
        "done": done,
        "open": total - done
    }


@app.post(
    "/reset",
    summary="Reset tasks",
    description="Restores the initial task list."
)
def reset():
    tasks.clear()
    tasks.extend(
        task.copy()
        for task in INITIAL_TASKS
    )

    return {
        "message": "Tasks reset",
        "tasks": tasks
    }
