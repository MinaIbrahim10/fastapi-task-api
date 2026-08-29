# FastAPI Task API — SQLite Persistence

A persistent CRUD API built with FastAPI and SQLite.

This project is the database-backed evolution of the original in-memory Task API. The public API remains the same while the storage layer has been replaced with SQLite.

## Architecture

Before:

```text
Client -> FastAPI -> Python list in memory
```

Now:

```text
Client -> FastAPI -> SQL queries -> SQLite -> tasks.db
```

The client does not need to know where the data is stored.

## Why SQLite?

SQLite was chosen because it:

- requires no separate database server
- stores the complete database in one local file
- supports real SQL
- is lightweight and portable
- provides persistent storage across application restarts
- is ideal for learning relational database fundamentals

The database file is:

```text
tasks.db
```

It is created automatically when the application starts and is intentionally ignored by Git.

## Database Schema

The `tasks` table contains:

| Column | Type | Purpose |
|---|---|---|
| `id` | INTEGER | Primary key |
| `title` | TEXT | Task title |
| `done` | INTEGER | Completion status |
| `created_at` | TEXT | UTC creation timestamp |
| `updated_at` | TEXT | UTC modification timestamp |

Three sample tasks are inserted automatically only when the table is empty.

Restarting the application does not duplicate them.

## API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/` | API information |
| GET | `/health` | Health check |
| GET | `/tasks` | List tasks |
| GET | `/tasks/{id}` | Get one task |
| POST | `/tasks` | Create a task |
| PUT | `/tasks/{id}` | Update a task |
| DELETE | `/tasks/{id}` | Delete a task |
| GET | `/stats` | SQL-backed task statistics |
| POST | `/reset` | Restore sample tasks |

The CRUD API keeps the same behavior as the original in-memory version.

Unknown task IDs return HTTP `404`.

Invalid requests return HTTP `400`.

Successful task creation returns HTTP `201`.

Successful deletion returns HTTP `204`.

## Persistence

Task data is stored using SQLite SQL statements rather than an in-memory Python array.

For example:

```sql
SELECT id, title, done
FROM tasks
ORDER BY id;
```

Creating a task uses `INSERT`, updating uses `UPDATE`, and deleting uses `DELETE`.

Data remains available after the FastAPI process stops and starts again.

## SQL Exploration

The database was modified directly with SQLite to verify that API responses reflect database state immediately.

The following queries were executed manually:

```sql
SELECT * FROM tasks;

SELECT * FROM tasks WHERE done = 1;

SELECT COUNT(*) FROM tasks;

UPDATE tasks SET done = 1;

DELETE FROM tasks WHERE done = 1;
```

After running:

```sql
UPDATE tasks SET done = 1;
```

`GET /tasks` immediately returned every task with:

```json
"done": true
```

and `GET /stats` returned:

```json
{
  "total": 3,
  "done": 3,
  "open": 0
}
```

This proves that the API reads the current SQLite database state rather than relying on an in-memory copy.

## Extra Features

Beyond the core assignment requirements, this implementation includes several additional SQL-backed features.

### SQL Search

```http
GET /tasks?search=fastapi
```

Implemented using SQL `LIKE`.

### SQL Completion Filtering

```http
GET /tasks?done=true
```

Implemented using a SQL `WHERE` condition.

### SQL Pagination

```http
GET /tasks?limit=2&offset=1
```

Implemented using SQL `LIMIT` and `OFFSET`.

### SQL Statistics

```http
GET /stats
```

Statistics are calculated directly by SQLite instead of counting Python list items.

Example query:

```sql
SELECT
    COUNT(*) AS total,
    SUM(CASE WHEN done = 1 THEN 1 ELSE 0 END) AS completed
FROM tasks;
```

### Timestamps

Every database row stores:

- `created_at`
- `updated_at`

`created_at` records when the task is created.

`updated_at` changes whenever the task is modified.

### SQL Reset

```http
POST /reset
```

Restores the original three sample tasks using SQL operations.

## Database Screenshot

The repository includes a screenshot showing the SQLite `tasks` table.

```text
screenshots/sqlite-database.png
```

![SQLite tasks database](screenshots/sqlite-database.png)

## Setup

Clone the repository:

```bash
git clone https://github.com/MinaIbrahim10/fastapi-task-api.git
cd fastapi-task-api
git switch w3-a1-sqlite-persistence
```

Create a virtual environment:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Start the API:

```bash
uvicorn main:app --reload
```

Open the interactive API documentation:

```text
http://127.0.0.1:8000/docs
```

The SQLite database and `tasks` table are created automatically when the application starts.

## Example Requests

### List all tasks

```bash
curl http://127.0.0.1:8000/tasks
```

### Get one task

```bash
curl http://127.0.0.1:8000/tasks/1
```

### Create a task

```bash
curl -X POST http://127.0.0.1:8000/tasks \
  -H 'Content-Type: application/json' \
  -d '{"title":"Persistent task"}'
```

Successful creation returns HTTP `201`.

### Update a task

```bash
curl -X PUT http://127.0.0.1:8000/tasks/1 \
  -H 'Content-Type: application/json' \
  -d '{"title":"Updated task","done":true}'
```

### Delete a task

```bash
curl -X DELETE http://127.0.0.1:8000/tasks/1
```

Successful deletion returns HTTP `204`.

### Search

```bash
curl 'http://127.0.0.1:8000/tasks?search=fastapi'
```

### Filter completed tasks

```bash
curl 'http://127.0.0.1:8000/tasks?done=true'
```

### Pagination

```bash
curl 'http://127.0.0.1:8000/tasks?limit=2&offset=1'
```

### Statistics

```bash
curl http://127.0.0.1:8000/stats
```

### Reset database tasks

```bash
curl -X POST http://127.0.0.1:8000/reset
```

## Persistence Verification

Create a new task:

```bash
curl -X POST http://127.0.0.1:8000/tasks \
  -H 'Content-Type: application/json' \
  -d '{"title":"Persist after restart"}'
```

Stop FastAPI and start it again:

```bash
uvicorn main:app --reload
```

Then request the tasks again:

```bash
curl http://127.0.0.1:8000/tasks
```

The newly created task remains present because it is stored in `tasks.db`.

The three initial example tasks are also inserted only when the table is empty, so repeated application restarts do not create duplicate seed data.

## Validation and Errors

Missing or empty titles return:

```text
HTTP 400 Bad Request
```

Example:

```json
{
  "error": "Title is required and cannot be empty"
}
```

Updating a task without supplying any fields returns:

```text
HTTP 400 Bad Request
```

Unknown task IDs return:

```text
HTTP 404 Not Found
```

Example:

```json
{
  "error": "Task 999 not found"
}
```

## Automated Tests

Run:

```bash
python -m pytest -q
```

The test suite verifies:

- automatic database initialization
- seed tasks are inserted only once
- database-backed task reads
- unknown task 404 handling
- task creation
- database persistence
- task updates
- task deletion
- HTTP 400 validation
- SQL search
- SQL completion filtering
- SQL pagination
- SQL statistics
- SQL-backed reset behavior

## Manual SQL Verification

The database can be inspected directly with the SQLite CLI:

```bash
sqlite3 tasks.db
```

Useful commands:

```sql
.headers on
.mode column
SELECT * FROM tasks;
```

Example completed-task query:

```sql
SELECT * FROM tasks WHERE done = 1;
```

Count all rows:

```sql
SELECT COUNT(*) FROM tasks;
```

Mark all tasks as complete:

```sql
UPDATE tasks SET done = 1;
```

Delete completed tasks:

```sql
DELETE FROM tasks WHERE done = 1;
```

Changes made directly in SQLite are immediately visible through the API because all task reads come from the database.

## Project Structure

```text
fastapi-task-api/
├── main.py
├── requirements.txt
├── README.md
├── .gitignore
├── screenshots/
│   └── sqlite-database.png
├── tests/
│   └── test_api.py
└── tasks.db
```

`tasks.db` is generated locally and ignored by Git.

## Assignment Evolution

The purpose of this version is to demonstrate that persistence can change without changing the public API.

Assignment 1 architecture:

```text
Client -> API -> Python list
```

Current architecture:

```text
Client -> API -> SQL -> SQLite
```

From the client's perspective:

```text
Same endpoints
Same request bodies
Same response behavior
Different storage implementation
```

This separation between the API layer and data layer is one of the foundations of backend engineering.

The original in-memory Assignment 1 implementation remains available on the `main` branch.

The SQLite-backed implementation for W3 · A1 is available on:

```text
w3-a1-sqlite-persistence
```

## Technologies

- Python 3.13
- FastAPI
- SQLite
- Pydantic
- Uvicorn
- Pytest
- HTTPX

## Status

Core assignment requirements:

- [x] Same CRUD API as Assignment 1
- [x] SQLite persistence
- [x] Automatic database creation
- [x] Automatic table creation
- [x] Three first-run example tasks
- [x] Persistent data across restarts
- [x] SQL-based reads
- [x] SQL-based inserts
- [x] SQL-based updates
- [x] SQL-based deletes
- [x] HTTP 404 for unknown IDs
- [x] HTTP 400 validation
- [x] Manual SQL exploration

Extra features:

- [x] SQL search
- [x] SQL completion filtering
- [x] SQL pagination
- [x] SQL statistics
- [x] created_at timestamps
- [x] updated_at timestamps
- [x] SQL-backed reset endpoint
- [x] automated API/database tests

## Additional Stretch Work

### Alphabetical Sorting

Tasks can be sorted alphabetically by title:

```http
GET /tasks?sort=title
```

This is implemented directly in SQLite with:

```sql
ORDER BY title COLLATE NOCASE;
```

Sorting is performed by the database rather than by a Python loop.

### Database Indexes

The project creates indexes for the columns used by search and filtering:

```sql
CREATE INDEX IF NOT EXISTS idx_tasks_title ON tasks(title);
CREATE INDEX IF NOT EXISTS idx_tasks_done ON tasks(done);
```

An index helps SQLite locate matching rows faster instead of scanning every row in the table, which becomes increasingly important as the dataset grows.

### Transactional Seeding

The initial three-task seed is wrapped in a database transaction.

This means the seed operation is all-or-nothing: either all starting rows are inserted successfully, or the transaction is rolled back instead of leaving the database partially initialized.

### Schema Changes and Migrations

Adding `created_at` and `updated_at` made the database schema more useful, but it also showed that changing a table's shape requires more care than changing an ordinary Python object.

That is why production projects use migrations: they provide a controlled and repeatable way to evolve a database schema while preserving existing data.

### API Compatibility Proof

The original Assignment 1 endpoint behavior has been preserved while the storage layer changed from an in-memory Python list to SQLite.

The automated test suite passes against the SQLite implementation:

```text
15 passed
```

The same endpoint contracts still hold:

- GET task endpoints return the same task response shapes.
- POST still returns `201`.
- DELETE still returns `204`.
- Invalid requests still return `400`.
- Unknown task IDs still return `404`.

Passing the API tests after replacing the storage layer demonstrates that the database is an implementation detail hidden behind the API contract.

## AI vs Me — Stage 6 Rematch

After completing the SQLite migration by hand, I asked an AI coding assistant to perform the same migration independently in the isolated `ai-version/` directory.

The hand-built implementation remained untouched during this experiment.

### First AI Prompt

```text
Act as a backend developer working with Python, FastAPI, and SQLite.

I have an existing in-memory CRUD Task API and I want you to migrate its storage layer to SQLite without changing the public API behavior.

Requirements:

- Keep the same CRUD endpoints:
  - GET /tasks
  - GET /tasks/{id}
  - POST /tasks
  - PUT /tasks/{id}
  - DELETE /tasks/{id}

- Use Python's built-in sqlite3 library.
- Store data in a local SQLite database file named tasks.db.
- Create a tasks table automatically if it does not exist.
- The tasks table must include id, title, and done.
- Seed exactly three example tasks only if the table is empty.
- Restarting the server must not duplicate seeded tasks.
- All CRUD operations must use SQLite.
- Missing or empty titles must return HTTP 400.
- Unknown task IDs must return HTTP 404.
- Successful creation must return HTTP 201.
- Successful deletion must return HTTP 204.
- Use parameterized SQL queries with ? placeholders.
- Data must survive server restarts.
- Do not use an ORM or unnecessary dependencies.
```

### First AI Attempt

The first AI implementation was stored in:

```text
ai-version/main.py
```

I ran it independently from my hand-built version and tested the complete CRUD and persistence flow.

The first AI version successfully:

- created its SQLite database automatically
- created and seeded the tasks table
- avoided duplicate seed rows after restart
- returned `200` for reads and updates
- returned `201` for creation
- returned `204` for deletion
- returned `400` for invalid input
- returned `404` for unknown task IDs
- persisted a newly created task after restarting the server
- used parameterized SQL queries

After creating one additional task and restarting the application, the database contained exactly four rows. This proved that persistence worked and the seed data was not duplicated.

### What the AI Did Better

The AI generated a much smaller implementation focused directly on the required CRUD migration.

Its storage flow was easy to follow:

```text
request -> SQL query -> SQLite -> response
```

It also produced working parameterized SQL and persistence on its first generated attempt.

This demonstrated how quickly an AI assistant can create a compact baseline when the specification is focused.

### What the AI Got Wrong or Quietly Changed

The first attempt also revealed several problems.

#### 1. It changed the seed data

My original seed tasks were:

```text
Learn FastAPI
Build CRUD API
Push project to GitHub
```

The first AI version generated:

```text
Learn FastAPI
Build Task API
Test the API
```

The database worked, but the existing application's data was not preserved exactly.

#### 2. It changed an error response

For an invalid POST request, the first AI implementation returned:

```json
{"error":"Invalid request data"}
```

My hand-built version returned:

```json
{"error":"Title is required and cannot be empty"}
```

The HTTP status code was correct, but the response contract was not identical.

#### 3. It only implemented the core migration

My hand-built implementation also includes:

- SQL search
- completion filtering
- alphabetical sorting
- pagination
- SQL statistics
- timestamps
- database indexes
- transactional seeding
- reset behavior
- automated tests

The AI did not include these because the first prompt did not request them.

This showed that the AI cannot reliably infer requirements that were never explicitly specified.

### What My First Prompt Forgot

The first prompt left several details open to interpretation.

It did not precisely specify:

- the exact three seed task titles
- every exact JSON error response
- partial update behavior
- every detail of the existing API contract
- which existing behavior had to remain identical

The AI therefore made reasonable choices for those unspecified details.

The main lesson was that saying "keep the same behavior" is weaker than explicitly defining the behavior that must remain unchanged.

### First Diff

I compared the first AI implementation with my hand-built version using:

```bash
git diff --no-index main.py ai-version/main.py
```

The complete diff is stored in:

```text
ai-version/diff-v1.txt
```

The diff showed a large difference in implementation size and scope because my hand-built version includes the core migration plus the optional extras and stretch work.

## Rematch

After reviewing the first AI attempt, I improved the prompt to remove the ambiguities I had discovered.

### Improved Prompt — V2

```text
Act as a backend developer working with Python, FastAPI, and SQLite.

Migrate an existing in-memory CRUD Task API to SQLite while preserving the existing API contract exactly.

Use Python's built-in sqlite3 library. Do not use an ORM.

The SQLite database must be named tasks.db and created automatically.

Create a tasks table automatically if it does not exist with:

- id INTEGER PRIMARY KEY
- title TEXT NOT NULL
- done INTEGER NOT NULL DEFAULT 0

Seed exactly these three tasks only when the table is empty:

1. id=1, title="Learn FastAPI", done=false
2. id=2, title="Build CRUD API", done=false
3. id=3, title="Push project to GitHub", done=false

Restarting the application must never duplicate these rows.

Preserve exactly these endpoints:

- GET /tasks
- GET /tasks/{id}
- POST /tasks
- PUT /tasks/{id}
- DELETE /tasks/{id}

GET /tasks must return:

{"id": integer, "title": string, "done": boolean}

Unknown task IDs must return HTTP 404 with:

{"error":"Task <id> not found"}

POST /tasks must reject missing, null, empty, or whitespace-only titles with HTTP 400:

{"error":"Title is required and cannot be empty"}

Valid titles must be stripped of surrounding whitespace.

Successful creation must return HTTP 201.

PUT /tasks/{id} must allow title, done, or both.

If neither field is supplied, return HTTP 400:

{"error":"At least one field is required"}

An empty or whitespace-only title must return HTTP 400:

{"error":"Title cannot be empty"}

Successful updates return HTTP 200.

DELETE /tasks/{id} must return HTTP 204 with an empty body.

Every CRUD operation must read from or write to SQLite.

No in-memory task list may be used as application storage.

Data must survive application restarts.

All user-provided values must use ? placeholders.

Never concatenate user input into SQL strings.

Keep the implementation simple and readable.

Do not add search, sorting, statistics, timestamps, indexes, reset endpoints, or unrelated extras.
```

### Rematch Result

The second AI implementation was generated as:

```text
ai-version/main-v2.py
```

The V2 implementation produced exactly the intended seed rows:

```text
1  Learn FastAPI
2  Build CRUD API
3  Push project to GitHub
```

An unknown ID returned:

```json
{"error":"Task 999 not found"}
```

A POST request with a missing title returned exactly:

```json
{"error":"Title is required and cannot be empty"}
```

Creating a task returned HTTP `201`.

After restarting the V2 server, the newly created task was still present.

The database contained exactly four rows after restart:

```text
3 seed rows + 1 created task = 4
```

This proved persistence worked without duplicated seeds.

Updating the task returned HTTP `200`.

Deleting it returned HTTP `204` with an empty body.

Requesting the deleted task returned HTTP `404`.

### V1 vs V2

I compared both AI-generated implementations using:

```bash
git diff --no-index ai-version/main.py ai-version/main-v2.py
```

The resulting diff is stored at:

```text
ai-version/diff-v1-v2.txt
```

The comparison reported:

```text
34 insertions
29 deletions
```

The important change was not code quantity. V2 followed the intended API contract more accurately because the second prompt converted previously implicit expectations into explicit requirements.

### Hand-Built vs V2

I also compared the improved AI version with my hand-built implementation:

```bash
git diff --no-index main.py ai-version/main-v2.py
```

That diff is stored at:

```text
ai-version/diff-hand-v2.txt
```

The hand-built implementation remains larger because it contains the core assignment plus optional extras and stretch work.

### What Changed in the Rematch

The second prompt explicitly defined:

- the exact seed rows
- exact validation messages
- exact 404 messages
- status-code behavior
- partial update rules
- persistence requirements
- parameterized SQL requirements
- the prohibition on using an in-memory task list as storage

Those details removed the assumptions made by the first AI attempt.

### Lesson Learned

The experiment demonstrated that AI-generated code can be fast and functional, but correctness depends heavily on specification quality.

Building the migration manually first made it possible to recognize subtle contract changes rather than accepting code simply because it ran successfully.

The rematch showed that reviewing AI output, identifying specification gaps, and improving the prompt can produce a much more precise implementation.


## Exact AI Prompt Records

### Prompt V1 — Original

```text
Act as a backend developer working with Python, FastAPI, and SQLite.

I have an existing in-memory CRUD Task API and I want you to migrate its storage layer to SQLite without changing the public API behavior.

Requirements:

- Keep the same CRUD endpoints:
  - GET /tasks
  - GET /tasks/{id}
  - POST /tasks
  - PUT /tasks/{id}
  - DELETE /tasks/{id}

- Use Python's built-in sqlite3 library.

- Store data in a local SQLite database file named tasks.db.

- Create a tasks table automatically if it does not exist.

- The tasks table must include:
  - id as an integer primary key
  - title as text
  - done stored as 0 or 1

- Seed exactly three example tasks only if the tasks table is empty.
- Restarting the server must not duplicate the seeded tasks.

- GET /tasks must read tasks from SQLite.
- GET /tasks/{id} must query SQLite by id.
- POST /tasks must insert a new task into SQLite and let SQLite generate the id.
- PUT /tasks/{id} must update the matching database row.
- DELETE /tasks/{id} must delete the matching database row.

Keep the same validation and HTTP behavior as the existing API:

- Missing or empty title -> HTTP 400 with a JSON error response.
- Unknown task id -> HTTP 404 with a JSON error response.
- Successful creation -> HTTP 201.
- Successful deletion -> HTTP 204 with an empty response body.
- Normal successful reads and updates -> HTTP 200.

Use parameterized SQL queries with ? placeholders for every value that comes from user input. Do not build SQL by concatenating user-provided values.

The data must survive stopping and restarting the FastAPI server.

Keep the implementation simple and readable. Do not add an ORM or unnecessary dependencies.

Return the complete working Python code for the migrated API and briefly explain:
1. how database initialization works,
2. how seeding avoids duplicates,
3. how each CRUD endpoint now talks to SQLite,
4. where parameterized queries are used.

```

### Prompt V2 — Rematch

```text
Act as a backend developer working with Python, FastAPI, and SQLite.

I have an existing in-memory CRUD Task API and I want you to migrate only its storage layer to SQLite while preserving the existing API contract exactly.

Use Python's built-in sqlite3 library. Do not use an ORM.

The SQLite database file must be named tasks.db and must be created automatically.

Create a tasks table automatically if it does not exist with these columns:

- id INTEGER PRIMARY KEY
- title TEXT NOT NULL
- done INTEGER NOT NULL DEFAULT 0

Seed exactly these three tasks, and only when the table is empty:

1. id=1, title="Learn FastAPI", done=false
2. id=2, title="Build CRUD API", done=false
3. id=3, title="Push project to GitHub", done=false

Restarting the application must never duplicate the seed rows.

Preserve these CRUD endpoints:

- GET /tasks
- GET /tasks/{id}
- POST /tasks
- PUT /tasks/{id}
- DELETE /tasks/{id}

Required behavior:

GET /tasks
- Return all tasks.
- Preserve the response shape:
  {"id": integer, "title": string, "done": boolean}

GET /tasks/{id}
- Query SQLite using a parameterized query.
- Unknown IDs must return HTTP 404 with:
  {"error":"Task <id> not found"}

POST /tasks
- Missing, null, empty, or whitespace-only titles must return HTTP 400 with:
  {"error":"Title is required and cannot be empty"}
- Strip surrounding whitespace from valid titles.
- Insert using a parameterized SQL query.
- Let SQLite generate the new id.
- New tasks must have done=false.
- Successful creation must return HTTP 201.

PUT /tasks/{id}
- Allow title, done, or both to be updated.
- A body containing neither field must return HTTP 400 with:
  {"error":"At least one field is required"}
- An empty or whitespace-only title must return HTTP 400 with:
  {"error":"Title cannot be empty"}
- Unknown IDs must return HTTP 404 with:
  {"error":"Task <id> not found"}
- Use parameterized SQL.
- Successful updates return HTTP 200.

DELETE /tasks/{id}
- Unknown IDs must return HTTP 404 with:
  {"error":"Task <id> not found"}
- Use a parameterized SQL DELETE.
- Successful deletion must return HTTP 204 with an empty body.

Persistence requirements:

- Every CRUD operation must read from or write to SQLite.
- No in-memory task list may be used as application storage.
- Data must survive stopping and restarting the server.
- Seed rows must only be inserted when the table is empty.
- All user-provided values must use ? placeholders.
- Never concatenate user input into SQL strings.

Keep the code simple, explicit, and readable.

Do not add search, sorting, statistics, timestamps, indexes, reset endpoints, or other extras. This rematch is specifically about reproducing the original CRUD API contract accurately.

Return a complete working FastAPI implementation.

```
