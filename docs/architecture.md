# Architecture

This page explains how the pieces fit together and why each one exists. For the
commands that set it all up, see [runbook.md](runbook.md).

## The picture

```
  browser / curl
       │  http://localhost:8080
       ▼
┌──────────────┐   Docker (compose.yaml, network_mode: host)
│ Nginx :8080  │   reverse proxy
└──────┬───────┘
       │  proxy_pass http://127.0.0.1:8000
       ▼
┌──────────────────┐   systemd user service: pastebin-app.service
│ uvicorn :8000    │   runs app.main:app (FastAPI)
│  routes          │
│   └─ service     │
│       └─ repo ───┼──────────┐
└──────────────────┘          │  postgresql://127.0.0.1:5442
                              ▼
                     ┌──────────────────┐   Docker (compose.yaml)
                     │ PostgreSQL :5442 │   data in volume "pgdata"
                     └──────────────────┘
                              ▲
                              │  DELETE ... WHERE expires_at <= now()
          ┌───────────────────┴───────────────────┐
          │                                       │
 systemd timer (every minute)              cron (every minute)
 pastebin-cleanup.timer                    deploy/cron/pastebin-cleanup.cron
   → pastebin-cleanup.service                → python -m app.cleanup
     → python -m app.cleanup                   (logs → logs/cleanup-cron.log)
       (logs → journalctl)
```

There are four long-running or scheduled things, each managed differently:

| Piece | What runs it | Why that way |
|---|---|---|
| PostgreSQL | Docker Compose | Nothing to install system-wide; the version is pinned in `compose.yaml`. |
| Nginx | Docker Compose | Same reason. Its only job is forwarding requests. |
| The app | systemd user service | How you'd run your own Python code on a VPS: a process systemd keeps alive and logs. |
| Cleanup | systemd timer **and** cron | So you can compare the two schedulers side by side. |

## Code layout

```
app/
  main.py         builds the FastAPI app, wires routers, /healthz
  routes/api.py   JSON:  POST /api/pastes, GET /api/pastes/{id}
  routes/web.py   HTML:  GET /, POST /, GET /{id}
  service.py      rules: lifetimes, size limit, ID generation
  repository.py   SQL:   insert, get-if-not-expired, delete-expired
  models.py       the "pastes" table as a Python class
  db.py           connection pool and per-request sessions
  config.py       settings from environment / .env
  cleanup.py      the scheduled job (python -m app.cleanup)
migrations/       Alembic: versioned schema changes
tests/            pytest, against a real Postgres
```

A request moves down the layers and each layer has one job:

- **Routes** speak HTTP. They read the request and call the service. They also turn the service's
  errors into status codes. `routes/api.py` and `routes/web.py` call the same service
  functions; one returns JSON and the other returns HTML. That shows the value of the
  service layer: two interfaces and one set of rules.
- **Service** decides what is allowed. `create_paste` rejects empty text, text over
  512 KiB and unknown lifetimes, and doesn't know whether the caller is a browser or `curl`.
- **Repository** is the only place with SQL. The cleanup job reuses
  `delete_expired` from here without touching any web code.

Dependencies only point downward. `repository.py` never imports from `routes/`. That rule
is what lets `cleanup.py` reuse the bottom layers without dragging in FastAPI.

## Expiry has two layers

This is the main design idea in the project.

1. **Reads check the clock.** `repository.get_live_paste` only returns a row if
   `expires_at > now()`. A paste is unreachable the moment it expires, whether or
   not anything has deleted it.
2. **A scheduled job deletes old rows.** `python -m app.cleanup` runs
   `DELETE FROM pastes WHERE expires_at <= now()` every minute.

The job exists to reclaim disk space, not for correctness. If cron and the timer
both stopped for a week, users would see exactly the same behavior. The table would
just grow. Keeping correctness out of the background job means a late, failed or
doubled job can't serve stale data.

The delete is also *idempotent*: running it twice in a row does no harm, because
the second run finds nothing to delete. That is why it's safe to schedule it with
cron and the systemd timer at the same time here. In a real deployment you'd pick one.

Both checks use the database's `now()`, not Python's clock, so the app and
the job always agree on what "expired" means. The `expires_at` column is indexed
because both queries filter on it.

## Cron vs systemd timer

| | cron | systemd timer |
|---|---|---|
| Schedule syntax | `* * * * *` (5 fields) | `OnCalendar=minutely` (check with `systemd-analyze calendar`) |
| Environment | Almost empty. You `cd`, load `.env`, and use full paths yourself. | `WorkingDirectory=` and `EnvironmentFile=` in the unit |
| Logs | Whatever you redirect to a file (`>> logs/cleanup-cron.log`) | journald: `journalctl --user -u pastebin-cleanup` |
| Failure visibility | Silent unless you read the log | `systemctl --user status` shows the last result and exit code |
| Missed runs (machine off) | Skipped | `Persistent=true` runs once on wake-up |
| Overlap | Two slow runs can overlap | A oneshot service won't start again while it's still running |
| Where it lives | Your crontab (`crontab -l`) | Unit files you can keep in git |

Cron is everywhere and simple to read. Timers give you logging, status and
dependency handling for free. Both are steps on the way to proper task queues
(Celery, RQ, cloud schedulers), which add retries, distribution across machines
and per-task visibility.

## How this differs from a real VPS

- **Linger.** User services only run while you're logged in. On a server you'd
  either run `loginctl enable-linger <user>` (user services start at boot) or install
  system units in `/etc/systemd/system/` with a `User=` line. This project skips both
  to keep everything inside the folder.
- **Dedicated user.** A server would run the app as an unprivileged `pastebin` user,
  not your login.
- **TLS.** Nginx would listen on 443 with a certificate (e.g. from Let's Encrypt via
  certbot) and redirect port 80 to it.
- **Firewall.** Only 80/443 (and SSH) open. Postgres here is already bound to
  127.0.0.1, which is the right habit.
- **Secrets.** The database password lives in plain `compose.yaml` and `.env` here;
  a server would keep them out of git.
- **Running the app.** One uvicorn worker is fine here. A busier server would run
  several workers, for example with `--workers 4` or gunicorn with uvicorn workers.
