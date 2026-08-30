# FastAPI Task API

Set a database password and start the stack:

```sh
POSTGRES_PASSWORD=change-me docker compose up --build
```

The API is available at <http://localhost:8000> and its interactive documentation
is at <http://localhost:8000/docs>. PostgreSQL data is kept in the named
`postgres_data` volume. The API starts only after PostgreSQL and Redis pass
their health checks, then verifies Redis with `PING`. `GET /health` checks the
PostgreSQL connection with `SELECT 1`.

Example request:

```sh
curl -X POST http://localhost:8000/tasks \
  -H 'Content-Type: application/json' \
  -d '{"title":"Write documentation"}'
```
