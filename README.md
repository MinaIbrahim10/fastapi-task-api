# FastAPI Task API — PostgreSQL + Docker Compose

A production-style FastAPI CRUD service backed by PostgreSQL and containerized with Docker Compose.

This version completes the third storage evolution of the project:

**In-memory → SQLite → PostgreSQL in Docker**

The HTTP API contract remains stable while persistence is moved behind a PostgreSQL repository.

---

## Stack

- Python 3.13
- FastAPI
- PostgreSQL 17
- Psycopg 3
- Redis 7
- Docker
- Docker Compose
- Pytest

The Compose stack contains three services:

```text
api      FastAPI application
db       PostgreSQL database
redis    Redis service
```

---

## Quick Start

Clone the repository, create the local environment file, and start the entire stack:

```bash
cp .env.example .env
docker compose up --build
```

The API will be available at:

```text
http://localhost:8000
```

Interactive Swagger documentation:

```text
http://localhost:8000/docs
```

Stop the stack with:

```bash
docker compose down
```

Do **not** use `docker compose down -v` if you want to preserve PostgreSQL data.

---

## Environment Variables

The public `.env.example` contains safe development placeholders:

```env
POSTGRES_DB=tasks
POSTGRES_USER=postgres
POSTGRES_PASSWORD=change-me
DATABASE_URL=postgresql://postgres:change-me@localhost:5432/tasks
```

Inside Docker Compose, the API connects to PostgreSQL through the Docker service hostname:

```text
db:5432
```

No real local credentials are committed to the repository.

---

## API Endpoints

| Method | Endpoint | Purpose | Success |
|---|---|---|---|
| GET | `/` | API information | `200` |
| GET | `/health` | Database health check | `200` |
| GET | `/tasks` | List tasks | `200` |
| GET | `/tasks/{id}` | Get one task | `200` |
| POST | `/tasks` | Create task | `201` |
| PUT | `/tasks/{id}` | Update task | `200` |
| DELETE | `/tasks/{id}` | Delete task | `204` |
| GET | `/stats` | Task statistics | `200` |
| POST | `/reset` | Restore original seed tasks | `200` |

Unknown task IDs return:

```text
404 Not Found
```

Invalid task payloads return:

```text
400 Bad Request
```

---

## Query Features

`GET /tasks` supports the previous API features:

```text
?done=true
?search=fastapi
?sort=title
?limit=2&offset=1
```

Examples:

```bash
curl http://localhost:8000/tasks
```

```bash
curl http://localhost:8000/tasks/1
```

```bash
curl 'http://localhost:8000/tasks?done=false'
```

```bash
curl 'http://localhost:8000/tasks?search=fastapi'
```

```bash
curl 'http://localhost:8000/tasks?sort=title'
```

Create:

```bash
curl -X POST \
  http://localhost:8000/tasks \
  -H 'Content-Type: application/json' \
  -d '{"title":"Learn Docker Compose"}'
```

Update:

```bash
curl -X PUT \
  http://localhost:8000/tasks/1 \
  -H 'Content-Type: application/json' \
  -d '{"title":"Updated task","done":true}'
```

Delete:

```bash
curl -X DELETE \
  http://localhost:8000/tasks/1
```

---

## PostgreSQL Initialization

The application automatically creates the `tasks` table when needed.

Initial schema:

```sql
CREATE TABLE IF NOT EXISTS tasks (
    id BIGSERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    done BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

Three tasks are seeded only when the table is empty:

```text
1  Learn FastAPI
2  Build CRUD API
3  Push project to GitHub
```

Repeated application restarts do not duplicate the seed data.

All user-controlled SQL values use Psycopg parameterized queries.

---

## Persistent PostgreSQL Volume

PostgreSQL uses the Compose named volume:

```text
taskdata
```

A persistence test was performed by:

1. Creating a new task through the API.
2. Confirming the row directly in PostgreSQL.
3. Running `docker compose down`.
4. Running `docker compose up`.
5. Requesting the same task again.

Result:

```text
PASS: row survived docker compose down/up
```

This proves that database state is stored outside the lifecycle of the container.

---

## Health Check

`GET /health` performs a real PostgreSQL round trip using:

```sql
SELECT 1;
```

Healthy response:

```json
{
  "status": "ok",
  "db": "ok"
}
```

This type of endpoint can be used by Docker, load balancers, and orchestration systems to determine whether the application is ready to receive traffic.

---

## Redis Extra

Redis runs as a third Compose service.

The API performs a Redis `PING` during application startup.

Direct verification:

```text
PONG
```

The Redis service demonstrates how the application stack can support additional infrastructure such as:

- caching
- sessions
- counters
- queues
- temporary state

PostgreSQL remains the permanent source of truth for tasks.

---

## Mortality Experiment

A separate PostgreSQL container was started without retaining a persistent volume.

A table and row were created:

```text
THIS DATA SHOULD DIE
```

The container and its anonymous volume were then destroyed.

A completely new PostgreSQL container was started and the previous table no longer existed.

Result:

```text
PASS — non-persistent container state disappeared.
```

Evidence:

```text
docs/evidence/mortality-experiment.txt
```

This contrasts with the main Compose database, whose data survives container recreation through the named volume.

---

## PostgreSQL Index Experiment

The production schema contains an index for the task completion filter:

```sql
CREATE INDEX IF NOT EXISTS idx_tasks_done
ON tasks(done);
```

A reproducible benchmark generated 100,000 rows and compared:

```sql
EXPLAIN ANALYZE
SELECT id, title, done
FROM task_index_benchmark
WHERE done = TRUE;
```

Before the index:

```text
Seq Scan
```

After the index:

```text
Index Scan
```

Observed execution time dropped from approximately:

```text
3.095 ms
```

to approximately:

```text
0.414 ms
```

Full evidence:

```text
docs/evidence/index-benchmark.txt
```

---

## Multi-Stage Docker Optimization

The original single-stage Docker image measured:

```text
62.51 MiB
```

The optimized Alpine multi-stage image measured:

```text
37.70 MiB
```

Result:

```text
24.82 MiB saved
39.70% reduction
```

The runtime container also runs as a non-root user:

```text
uid=999(app) gid=999(app)
```

Evidence:

```text
docs/evidence/image-size-comparison.txt
```

---

## Docker Architecture

```text
                    ┌─────────────────────┐
                    │       Client        │
                    └──────────┬──────────┘
                               │
                               │ :8000
                               ▼
                    ┌─────────────────────┐
                    │       FastAPI       │
                    │        api          │
                    └──────┬────────┬─────┘
                           │        │
                    SQL    │        │ Redis
                           ▼        ▼
                ┌──────────────┐ ┌──────────────┐
                │ PostgreSQL   │ │    Redis     │
                │     db       │ │    redis     │
                └──────┬───────┘ └──────────────┘
                       │
                       ▼
                ┌──────────────┐
                │   taskdata   │
                │ named volume │
                └──────────────┘
```

---

## Repository Structure

```text
.
├── main.py
├── postgres_repository.py
├── redis_client.py
├── Dockerfile
├── compose.yaml
├── requirements.txt
├── requirements-dev.txt
├── .env.example
├── sql/
│   └── 001_create_tasks.sql
├── scripts/
│   └── index_benchmark.sql
├── tests/
│   ├── test_api.py
│   ├── test_postgres_reads.py
│   └── test_postgres_crud.py
└── docs/
    └── evidence/
        ├── mortality-experiment.txt
        ├── index-benchmark.txt
        └── image-size-comparison.txt
```

---

## Tests

Install development dependencies:

```bash
pip install -r requirements-dev.txt
```

PostgreSQL-backed test suites cover:

- reading
- filtering
- searching
- sorting
- pagination
- create
- update
- delete
- reset
- statistics
- health checking
- error status codes

The PostgreSQL CRUD/read checkpoint passed:

```text
17 passed
```

---

## Storage as an Implementation Detail

The external API still exposes the same task-oriented HTTP behavior used by the previous project stages.

The important architectural change is below the HTTP layer:

```text
Route
  ↓
PostgreSQL repository
  ↓
Psycopg parameterized SQL
  ↓
PostgreSQL
```

Database-specific SQL is kept out of the route handlers and centralized in `postgres_repository.py`.

This makes persistence an implementation detail rather than part of the API contract.

---

## Security Notes

- `.env` is ignored by Git.
- `.env.example` contains placeholders only.
- Database credentials are supplied through environment variables.
- SQL inputs use parameterized queries.
- PostgreSQL is not published to the host by Compose.
- Redis is not published to the host.
- The API container runs as a non-root user.
- Secrets are not embedded in the application source.

---

## Evidence

Technical experiment outputs are stored under:

```text
docs/evidence/
```

These include:

```text
mortality-experiment.txt
index-benchmark.txt
image-size-comparison.txt
```

A database screenshot should accompany the final submission showing the running PostgreSQL `tasks` table.

---

## Development Progression

This repository intentionally demonstrates three persistence stages:

```text
A1 — in-memory storage
A2 — SQLite persistence
A3 — containerized PostgreSQL persistence
```

The primary lesson is that application behavior can remain stable while infrastructure and persistence evolve underneath it.

---

## AI vs Me

For the AI comparison, I first wrote a short prompt from memory and asked an AI coding agent to build a PostgreSQL version of the same Task API inside a quarantined `ai-version/` directory.

### Prompt V1

```text
Build me a small FastAPI task API using Python and PostgreSQL.

Use psycopg to connect to the database. The database should have a tasks table with id, title, done, created_at, and updated_at.

When the app starts, create the table if it does not exist and insert 3 default tasks only if the table is empty.

I need these endpoints:
GET /tasks
GET /tasks/{id}
POST /tasks
PUT /tasks/{id}
DELETE /tasks/{id}

Use parameterized SQL queries, not string formatting.

The database password and connection details should come from environment variables, not be hardcoded.

Run PostgreSQL in Docker and use a persistent volume so the data survives container restarts.

Also create a Dockerfile and docker-compose setup so the whole project can be started with Docker Compose.

Keep the code simple and separated enough so the database code is not mixed everywhere inside the route handlers.
```

### What AI V1 did well

The first AI version successfully produced a working PostgreSQL-backed FastAPI service.

It correctly:

- used Psycopg and parameterized SQL;
- created the table automatically;
- seeded three tasks only when the table was empty;
- implemented the five CRUD endpoints;
- returned `201` for task creation;
- returned `404` for an unknown task;
- used environment-based database configuration;
- used a named PostgreSQL Docker volume;
- preserved a created task after a full `docker compose down` followed by `docker compose up`.

### Differences between AI V1 and my implementation

#### 1. Existing API contract

AI V1 returned:

```json
{
  "id": 4,
  "title": "Example",
  "done": false,
  "created_at": "...",
  "updated_at": "..."
}
```

My implementation preserved the original public Task API shape:

```json
{
  "id": 4,
  "title": "Example",
  "done": false
}
```

The storage migration therefore stayed an implementation detail instead of changing the public API.

#### 2. Error behavior

AI V1 used FastAPI's standard error format such as:

```json
{
  "detail": "Task not found"
}
```

My version preserved the error contract from the earlier assignment instead of silently changing endpoint behavior during the storage migration.

#### 3. Container design

AI V1 initially used a single-stage `python:3.13-slim` Docker image.

My implementation uses a multi-stage Alpine build, copies only the runtime virtual environment, and runs the application as a non-root user.

The measured image-size experiment reduced the image from approximately 62.51 MiB to 37.70 MiB, a reduction of about 39.70%.

#### 4. Health checking

AI V1 did not initially include a real API health check.

My implementation provides `/health` and performs an actual PostgreSQL `SELECT 1` round trip. The Docker image also has an HTTP `HEALTHCHECK`, allowing Docker or an orchestrator/load balancer to distinguish a running process from a healthy service.

#### 5. Redis integration

AI V1 only created the API and PostgreSQL services.

My implementation also includes Redis in Docker Compose, verifies it with `PING`, and waits for both PostgreSQL and Redis health before starting the API.

#### 6. Additional database behavior

My implementation also retains the earlier API features such as filtering, searching, sorting, pagination, statistics, and reset behavior while keeping SQL access isolated in the repository layer.

### Rematch

After reviewing V1, I wrote a second prompt describing the missing production-style requirements.

```text
Improve the PostgreSQL FastAPI version you created in ai-version.

Keep the same five CRUD endpoints, but this time preserve the existing Task API behavior exactly. Responses should only expose id, title, and done. Unknown task IDs should return a JSON error response with the same style as the existing API.

Keep all SQL parameterized and database configuration in environment variables.

Also improve the Docker setup:
- use a multi-stage Alpine build
- run the API container as a non-root user
- add a real API health check
- add Redis as another Compose service and verify it with PING at startup
- make the API wait for PostgreSQL and Redis health
- keep PostgreSQL data in a named volume

Add a GET /health endpoint that checks PostgreSQL with SELECT 1.

Keep database code separated from route handlers.

Do not modify anything outside ai-version/.
```

### AI V2 result

The rematch corrected the main V1 weaknesses.

V2:

- restored responses to `id`, `title`, and `done`;
- restored the previous validation/error behavior;
- added a PostgreSQL-backed `/health`;
- added Redis and startup `PING`;
- added Compose health dependencies;
- changed to a multi-stage Alpine image;
- changed the API container to a non-root user;
- added an HTTP Docker health check;
- kept PostgreSQL in a named persistent volume.

The comparison showed that the initial AI prompt was enough to produce a functional CRUD system, but it did not automatically preserve all of the earlier API contract or include the production-oriented container features. Those appeared only after they were made explicit in the rematch prompt.

This was useful because it separated two different skills: generating a working implementation and engineering a migration that preserves existing behavior while improving operational quality.

