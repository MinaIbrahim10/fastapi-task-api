# FastAPI Task API

A simple in-memory CRUD API built with FastAPI.

The API allows users to create, read, update, and delete tasks. Data is stored only in memory, so tasks are reset whenever the server restarts.

## Features

- Create tasks
- List all tasks
- Get a task by ID
- Update task title and completion status
- Delete tasks
- Input validation
- Proper HTTP status codes
- Health-check endpoint
- Interactive Swagger UI documentation

## Tech Stack

- Python 3.10+
- FastAPI
- Uvicorn
- Pydantic
- Swagger UI / OpenAPI

## Project Structure

```text
fastapi-task-api/
├── main.py
├── requirements.txt
├── README.md
└── docs/
    └── swagger.png
```

## Installation

Clone the repository:

```bash
git clone https://github.com/MinaIbrahim10/fastapi-task-api.git
cd fastapi-task-api
```

Create a virtual environment:

```bash
python -m venv .venv
```

Activate it:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## Run the API

Start the development server:

```bash
uvicorn main:app --reload
```

The API will be available at:

```text
http://localhost:8000
```

Swagger UI:

```text
http://localhost:8000/docs
```

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/` | API information |
| GET | `/health` | Health check |
| GET | `/tasks` | List all tasks |
| GET | `/tasks/{task_id}` | Get a task by ID |
| POST | `/tasks` | Create a new task |
| PUT | `/tasks/{task_id}` | Update an existing task |
| DELETE | `/tasks/{task_id}` | Delete a task |

## Example Task

```json
{
  "id": 1,
  "title": "Learn FastAPI",
  "done": false
}
```

## Create a Task

```bash
curl -i -X POST http://localhost:8000/tasks \
-H "Content-Type: application/json" \
-d '{"title":"Buy milk"}'
```

Example response:

```text
HTTP/1.1 201 Created
content-type: application/json

{"id":4,"title":"Buy milk","done":false}
```

## Update a Task

```bash
curl -i -X PUT http://localhost:8000/tasks/4 \
-H "Content-Type: application/json" \
-d '{"title":"Buy groceries","done":true}'
```

Example response:

```json
{
  "id": 4,
  "title": "Buy groceries",
  "done": true
}
```

## Delete a Task

```bash
curl -i -X DELETE http://localhost:8000/tasks/4
```

Successful deletion returns:

```text
HTTP/1.1 204 No Content
```

## Validation

Creating a task without a title:

```bash
curl -i -X POST http://localhost:8000/tasks \
-H "Content-Type: application/json" \
-d '{}'
```

Returns:

```text
HTTP/1.1 400 Bad Request
```

```json
{
  "error": "Title is required and cannot be empty"
}
```

Requesting a task that does not exist:

```bash
curl -i http://localhost:8000/tasks/99
```

Returns:

```text
HTTP/1.1 404 Not Found
```

```json
{
  "error": "Task 99 not found"
}
```

## Status Codes

| Code | Meaning |
|---|---|
| `200 OK` | Successful read or update |
| `201 Created` | Task successfully created |
| `204 No Content` | Task successfully deleted |
| `400 Bad Request` | Invalid request body |
| `404 Not Found` | Requested task does not exist |

## Swagger UI

FastAPI automatically generates interactive API documentation using OpenAPI.

Open:

```text
http://localhost:8000/docs
```

The full CRUD cycle can be tested directly from Swagger UI using the **Try it out** button.

![Swagger UI](docs/swagger.png)

## Data Storage

This project intentionally uses in-memory storage instead of a database.

Tasks exist only while the application is running. Restarting the server resets the task list to the initial sample data.

## Git History

The project was developed incrementally with separate commits for each implementation stage:

- Hello server
- Root and health endpoints
- Read endpoints and 404 handling
- Create endpoint with validation
- Full CRUD
- Swagger UI
- Documentation and publishing
## Optional Extras

### Filtering

Tasks can be filtered by completion status:

```bash
curl "http://localhost:8000/tasks?done=true"
```

### Search

Tasks can be searched by title:

```bash
curl "http://localhost:8000/tasks?search=fastapi"
```

### Pagination

The API supports `limit` and `offset` query parameters:

```bash
curl "http://localhost:8000/tasks?limit=2&offset=1"
```

Pagination is important in real APIs because returning an entire large dataset in one response can waste memory, bandwidth, and processing time.

### Statistics

```bash
curl http://localhost:8000/stats
```

Example response:

```json
{
  "total": 3,
  "done": 0,
  "open": 3
}
```

### Reset

The original sample tasks can be restored with:

```bash
curl -X POST http://localhost:8000/reset
```

### In-Memory Mortality Experiment

I created an additional task and confirmed that it appeared in `GET /tasks`. After stopping and restarting the API server, the added task disappeared and only the initial sample tasks remained.

This happens because the application stores its data only in process memory. In-memory state is lost when the process stops, which is why persistent applications normally use a database or another durable storage system.
## AI vs Me

### First Prompt

I wrote the following prompt from memory after completing the original API:

```text
act with 3 agents 
first build a full fastapi appliction useing python 3.13+ it is about task u must add health endpoint to check API HEALTH GET
/ endpoint to get API information and it must return that 

{
  "name": "Task API",
  "version": "1.1",
  "endpoints": [
    "/tasks",
    "/stats",
    "/reset",
    "/health"
  ]
}

and endpoint to list all tasks GET
and endpoint to create new task it takes title and it must retrn the task handle 200 and 400 for evertything also hadnle 422 to act as 400 POST

and endpont TO GET TAKS BY ID IT TEKS THE ID AND RETURN THE TASK INFORMATION GET
an endpoitn to modify a tak takes ID mandatory and cahnge it information
{
  "title": "string",
  "done": true
} PUT

a delete endpoint by task id DELETE

get statcks about taks get nothing and it retrns this
{
  "total": 3,
  "done": 0,
  "open": 3
}

reset task to rest all tasks idk modify it if something msisin POST

the seond agent must create the full readme.md and reqiremtns.txt and give instructioncomamnds how to init and oush to github

the third agent must verify the whole process

handle status code 200 and 400 specilly for all of it
```

### First AI Attempt

The AI-generated implementation ran successfully and handled the basic API structure, health endpoint, task listing, validation, updates, statistics, reset, and 404 responses.

However, testing and comparing it with my implementation exposed several differences.

### Concrete Differences

1. **POST status code**

   My implementation returns `201 Created` when a task is created.

   The first AI implementation returned `200 OK`.

   My first prompt emphasized `200` and `400` but did not explicitly require `201`, so the AI made a reasonable but incorrect decision.

2. **DELETE behavior**

   My implementation returns `204 No Content` with an empty body after a successful deletion.

   The AI implementation returned `200 OK` and a JSON object containing the deleted task.

   I did not explicitly specify `204 No Content` in my first prompt.

3. **Filtering, search, and pagination**

   My implementation supports:

   - `GET /tasks?done=true`
   - `GET /tasks?search=text`
   - `GET /tasks?limit=N&offset=N`

   The first AI implementation did not include these features because my prompt never asked for them.

4. **Swagger documentation**

   Both versions receive Swagger UI automatically from FastAPI, but my implementation includes explicit summaries and descriptions for the endpoints.

   The first AI version created basic routes without these descriptions because I did not specify documentation quality in the prompt.

5. **Validation**

   The AI used a required Pydantic `title: str` field, while my implementation used an optional field followed by explicit business-rule validation.

   The AI approach is more concise for detecting a missing title, while my implementation gives me more direct control over the exact error response.

### What the AI Did Better

The first AI version used a concise Pydantic model with a required title and had a simpler control flow in parts of the update endpoint.

Reviewing it showed me that some validation responsibilities can be expressed directly in the schema rather than manually.

### What the AI Got Wrong or Missed

The most important misses were the `201` create status, `204` delete status, filtering, search, pagination, and detailed Swagger endpoint descriptions.

These were not random failures: most came directly from requirements that I had not specified precisely enough.

### What My Prompt Forgot

My first prompt did not clearly specify:

- `201 Created` for POST
- `204 No Content` for DELETE
- `404` for every unknown task ID
- in-memory storage
- filtering
- search
- pagination
- Swagger endpoint descriptions
- the exact three seed tasks
- empty response body for DELETE

The first comparison showed that the AI filled these gaps with its own assumptions.

### Rematch Prompt

For the rematch, I rewrote the prompt as a more explicit specification. I defined the storage model, every endpoint, filtering/search/pagination, seed data, JSON error format, validation behavior, and the exact `200`, `201`, `204`, `400`, and `404` status codes.

I also explicitly required Swagger documentation and asked a verifier agent to check the implementation against the specification.

### Rematch Result

The rematch corrected the major specification gaps: task creation uses `201 Created`, deletion uses `204 No Content`, invalid input maps to `400`, unknown IDs map to `404`, and the generated API includes filtering, search, pagination, statistics, reset behavior, and Swagger endpoint descriptions.

The main lesson from the rematch was that a more precise specification produced an implementation much closer to the intended API.
