from fastapi import FastAPI
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

app = FastAPI(
    title="Task API",
    version="1.0",
    description="A simple in-memory CRUD API for managing tasks."
)


tasks = [
    {"id": 1, "title": "Learn FastAPI", "done": False},
    {"id": 2, "title": "Build CRUD API", "done": False},
    {"id": 3, "title": "Push project to GitHub", "done": False},
]


class TaskCreate(BaseModel):
    title: str | None = None


class TaskUpdate(BaseModel):
    title: str | None = None
    done: bool | None = None


@app.get(
    "/",
    summary="API information",
    description="Returns basic information about the Task API."
)
def root():
    return {
        "name": "Task API",
        "version": "1.0",
        "endpoints": ["/tasks"]
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
    summary="List all tasks",
    description="Returns all tasks currently stored in memory."
)
def get_tasks():
    return tasks


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
    description="Creates a new task. The title is required and cannot be empty."
)
def create_task(task_data: TaskCreate):
    if task_data.title is None or not task_data.title.strip():
        return JSONResponse(
            status_code=400,
            content={"error": "Title is required and cannot be empty"}
        )

    title = task_data.title.strip()

    next_id = max(task["id"] for task in tasks) + 1 if tasks else 1

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
    description="Updates the title and/or completion status of an existing task."
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
