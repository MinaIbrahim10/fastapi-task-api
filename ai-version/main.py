from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel


app = FastAPI(
    title="Task API",
    version="1.1",
    description="A FastAPI application for managing tasks."
)


INITIAL_TASKS = [
    {"id": 1, "title": "Learn FastAPI", "done": False},
    {"id": 2, "title": "Build Task API", "done": False},
    {"id": 3, "title": "Test the API", "done": False},
]

tasks = [task.copy() for task in INITIAL_TASKS]


class TaskCreate(BaseModel):
    title: str


class TaskUpdate(BaseModel):
    title: str | None = None
    done: bool | None = None


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
):
    return JSONResponse(
        status_code=400,
        content={"error": "Invalid request data"},
    )


@app.get("/")
def api_information():
    return {
        "name": "Task API",
        "version": "1.1",
        "endpoints": [
            "/tasks",
            "/stats",
            "/reset",
            "/health",
        ],
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/tasks")
def list_tasks():
    return tasks


@app.post("/tasks")
def create_task(task_data: TaskCreate):
    title = task_data.title.strip()

    if not title:
        return JSONResponse(
            status_code=400,
            content={"error": "Title cannot be empty"},
        )

    new_task = {
        "id": max((task["id"] for task in tasks), default=0) + 1,
        "title": title,
        "done": False,
    }

    tasks.append(new_task)

    return new_task


@app.get("/tasks/{task_id}")
def get_task(task_id: int):
    for task in tasks:
        if task["id"] == task_id:
            return task

    return JSONResponse(
        status_code=404,
        content={"error": f"Task {task_id} not found"},
    )


@app.put("/tasks/{task_id}")
def update_task(task_id: int, task_data: TaskUpdate):
    for task in tasks:
        if task["id"] == task_id:
            if task_data.title is None and task_data.done is None:
                return JSONResponse(
                    status_code=400,
                    content={"error": "No update data provided"},
                )

            if task_data.title is not None:
                title = task_data.title.strip()

                if not title:
                    return JSONResponse(
                        status_code=400,
                        content={"error": "Title cannot be empty"},
                    )

                task["title"] = title

            if task_data.done is not None:
                task["done"] = task_data.done

            return task

    return JSONResponse(
        status_code=404,
        content={"error": f"Task {task_id} not found"},
    )


@app.delete("/tasks/{task_id}")
def delete_task(task_id: int):
    for index, task in enumerate(tasks):
        if task["id"] == task_id:
            deleted_task = tasks.pop(index)

            return {
                "message": "Task deleted",
                "task": deleted_task,
            }

    return JSONResponse(
        status_code=404,
        content={"error": f"Task {task_id} not found"},
    )


@app.get("/stats")
def stats():
    total = len(tasks)
    done = sum(1 for task in tasks if task["done"])

    return {
        "total": total,
        "done": done,
        "open": total - done,
    }


@app.post("/reset")
def reset_tasks():
    tasks.clear()
    tasks.extend(task.copy() for task in INITIAL_TASKS)

    return {
        "message": "Tasks reset successfully",
        "tasks": tasks,
    }
