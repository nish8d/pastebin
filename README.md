# Pastebin

A small pastebin built to learn backend structure, deployment and scheduled jobs on Linux.
You paste text, pick a lifetime from 1 minute to 1 week, and get a short link. After the
lifetime runs out the link returns 404, and a cleanup job running every minute deletes the
row.

Stack: FastAPI, PostgreSQL (SQLAlchemy + Alembic), Nginx, systemd user units, cron.
Everything runs locally. Postgres and Nginx run in Docker; the app and the cleanup job run
under systemd, the way they would on a VPS.

- [docs/architecture.md](docs/architecture.md): how the pieces fit, the code layers, the two-layer expiry design, and cron vs systemd timers
- [docs/runbook.md](docs/runbook.md): step-by-step deployment, with what to expect and how to check each step

## API

```bash
curl -X POST localhost:8080/api/pastes -H 'content-type: application/json' \
  -d '{"content": "hello", "ttl": "1h"}'          # ttl: 1m | 10m | 1h | 1d | 1w
curl localhost:8080/api/pastes/<id>
```

The interactive API docs are at http://localhost:8080/docs.

## Running the tests

The tests use a real, throwaway Postgres on port 5443, separate from the deployed one:

```bash
docker run -d --rm --name pastebin-testdb \
  -e POSTGRES_USER=pastebin -e POSTGRES_PASSWORD=pastebin -e POSTGRES_DB=pastebin_test \
  -p 127.0.0.1:5443:5432 postgres:17

uv run pytest

docker stop pastebin-testdb      # --rm deletes it once stopped
```

## Running the app without deploying

This uses the test database, which already has the table once you've run the tests:

```bash
DATABASE_URL=postgresql+psycopg://pastebin:pastebin@127.0.0.1:5443/pastebin_test \
  uv run uvicorn app.main:app --reload --port 8000
```
