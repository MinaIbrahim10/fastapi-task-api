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
