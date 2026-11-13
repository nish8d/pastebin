# Pastebin — Design

Date: 2026-11-06
Repo: https://github.com/nish8d/pastebin.git (currently empty)

## Intent

A learning project. The user wants to come away understanding three things well
enough to do them alone next time:

1. **Code structure** — how a small backend is organized and why.
2. **System design** — how the pieces (app, database, reverse proxy, scheduled
   job) fit together and what each is responsible for.
3. **Deployment and scheduled jobs on Linux** — systemd services, systemd
   timers, cron, and a reverse proxy, the way you'd run them on a VPS.

Claude writes the code. The user reads and learns from it, so clarity beats
cleverness everywhere. Explanatory docs are part of the deliverable, not an
afterthought.

## Product

A pastebin: paste text, choose a lifetime, get a short link. The link shows the
text until it expires; after that it is gone.

### Web pages (server-rendered HTML)

- `GET /` — textarea, expiry dropdown, "Create" button. Form posts to the app.
- On submit → redirect (303) to `/<short-id>`.
- `GET /<short-id>` — paste content in a monospace `<pre>` block, the expiry
  time, and a "copy link" button.
- Missing or expired paste → simple "not found or expired" page, HTTP 404.

Expiry options: **1 minute, 10 minutes, 1 hour, 1 day, 1 week**. The 1-minute
option exists so the user can watch cleanup happen.

### JSON API

- `POST /api/pastes` — body `{"content": str, "ttl": <one of the options>}`
  → `201` with `{id, url, expires_at}`.
- `GET /api/pastes/{id}` → `200` `{id, content, created_at, expires_at}` or `404`.

Same service layer backs both HTML and JSON — demonstrating one backend, two
interfaces.

### Non-goals (deliberately out)

Accounts/auth, editing pastes, syntax highlighting, rate limiting, burn-after-read,
HTTPS/TLS, a real VPS. Any can be a later exercise.

### Anti-goals (failure even if it "works")

- Code too clever or abstract for a learner to follow.
- Deployment hidden behind magic (one opaque script) so the user never sees the
  moving parts.
- Touching the system outside the project folder beyond the one agreed exception
  (below).

## Key design idea: two layers of expiry

1. **Correctness at read time.** Every read filters `expires_at > now()`. An
   expired paste is never served, even if cleanup hasn't run.
2. **Storage hygiene via a scheduled job.** A cleanup script deletes rows where
   `expires_at <= now()`. It is about disk space, not correctness.

The docs must explain this explicitly — it is the main system-design lesson.

## Constraints

- **Local only.** Everything runs on the user's Linux machine (Ubuntu-like,
  Python 3.12, `uv`, Docker + Compose v5, `systemctl`, `crontab`, `psql`
  client installed; no Postgres server or Nginx installed natively).
- **Stays inside `pastebin/`.** Single agreed exception: systemd *user* unit
  files live in the repo and are symlinked (or `systemctl --user link`ed) into
  `~/.config/systemd/user/`. No root, no system-wide installs. Cron uses the
  user's own crontab (also outside the folder by nature — documented
  install/uninstall commands).
- **Git:** commits authored solely by the user's git identity (`nish8d`), no
  Claude co-author trailers. Commit/push only at significant milestones.
  Global git identity is already configured (`nish8d`); verify, don't set it.
  Builder runs `git init`, adds the remote, and pushes at milestones (the user
  asked for pushes at milestones). This spec goes in the first commit.
  *(Claude's call on the last point.)*
- **Docker storage:** Postgres uses a Docker named volume; images and volumes
  living under `/var/lib/docker` is fine and doesn't count as "touching the
  system". *(Claude's call: Docker is already installed and this is its normal
  behavior. A bind mount inside the repo would bring file-ownership problems.)*
- **Lifetime:** no `loginctl enable-linger`. User services run while the user is
  logged in. The docs explain linger as the VPS difference rather than enabling
  it. Containers use Compose `restart: unless-stopped`. The app's service unit
  should cope with the database not being up yet, either by retrying or with
  `Restart=on-failure`. *(Claude's call: enabling linger writes outside the
  agreed exception.)*

## Decided "how"

- **App:** Python 3.12, FastAPI, managed with `uv`.
- **Database:** PostgreSQL, running in Docker (Compose).
- **Reverse proxy:** Nginx, running in Docker (Compose), proxying to the app on
  the host.
- **App process:** run by a systemd user service (uvicorn), as on a VPS.
- **Cleanup:** a standalone script/entrypoint, scheduled **both** ways — a
  systemd user timer *and* a cron entry — so the user can compare. Docs should
  say that in real life you'd pick one, and that running both is safe because
  the delete is idempotent.
- **Layout:** small layered structure — routes (HTML + API) → service →
  data access — plus config, templates, and the cleanup entrypoint.
- **Migrations:** Alembic.
- **Tests:** pytest.
- **Docs:** a `docs/` walkthrough covering architecture, each deployment piece
  (what it is, why it exists, how to inspect it: `systemctl --user status`,
  `journalctl --user -u ...`, `crontab -l`, nginx logs, `psql`), and the
  two-layer expiry idea.

## Who runs deployment (user decided)

**The user runs every command that changes the system**: `docker compose up`,
`systemctl --user link/enable/start`, installing the crontab entry. Claude
writes and tests all the code first. Then it writes a step-by-step runbook
(`docs/`) and walks through it one step at a time, stopping before each step.
After each step the user runs it, inspects the result (`systemctl --user
status`, `journalctl --user -u ...`, `crontab -l`, `docker compose ps`,
`curl`), and reports back. Each runbook step says what to run, what you should
see, and how to check it. Deployment milestones are verified from what the user
reports.

## Left to the builder

- Short-ID scheme (length, alphabet, collision handling).
- Sync vs async DB driver and ORM choice (keep it readable).
- Exact package/module names, config mechanism (env file is fine).
- Ports, container names, Compose details.
- Cleanup interval (something short enough to observe, e.g. every minute).
- Max paste size and validation details.
- How tests get a database.
- Styling — minimal, plain CSS is fine.
- Milestone breakdown for commits.
