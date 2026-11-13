# Deployment runbook

Each step changes something on your machine, so you run it yourself. Every step has:

- **Run**: the commands
- **You should see**: what normal output looks like
- **Check it**: how to confirm it worked

Run everything from the project folder:

```bash
cd ~/Desktop/pp/pastebin
```

How the pieces fit together is in [architecture.md](architecture.md).

## 0. Before you start

Stop any uvicorn you started by hand (Ctrl+C in that terminal). Port 8000 has to be free
for the systemd service. Also clear any `DATABASE_URL` you exported earlier. A
variable in your shell **overrides** `.env`, so you would silently be using the
test database.

**Run**

```bash
unset DATABASE_URL BASE_URL
ss -ltn | grep -E ':(8000|8080|5442) '
```

**You should see** no output from `ss`. If a port shows up, find out what's using it
with `ss -ltnp | grep <port>`.

## 1. Create the config file

**Run**

```bash
cp .env.example .env
cat .env
```

**You should see** `DATABASE_URL=...@127.0.0.1:5442/pastebin` and
`BASE_URL=http://localhost:8080`.

This one file is read by the app, by systemd (`EnvironmentFile=`) and by the cron job.
It's in `.gitignore`, so it never gets committed.

## 2. Start Postgres and Nginx

**Run**

```bash
docker compose up -d
docker compose ps
```

**You should see** two containers, `pastebin-db-1` and `pastebin-nginx-1`, with
status `Up`. After a few seconds the db shows `(healthy)`.

**Check it**

```bash
docker compose logs db | tail -3          # "database system is ready to accept connections"
docker compose exec nginx nginx -t        # "syntax is ok"
curl -s -o /dev/null -w '%{http_code}\n' localhost:8080
```

That `curl` should print `502` (Bad Gateway). Nginx is up but nothing is listening on
port 8000 yet. That's expected and shows Nginx is a separate process from the app.

## 3. Install dependencies and create the table

**Run**

```bash
uv sync
uv run alembic upgrade head
```

**You should see** `Running upgrade  -> 0001, Create the pastes table.`

**Check it**

```bash
docker compose exec db psql -U pastebin -c '\d pastes'
uv run alembic current        # "0001 (head)"
```

Alembic keeps track of which migrations have been applied in a table called
`alembic_version`. You can look at it with `docker compose exec db psql -U pastebin -c 'select * from alembic_version'`.

## 4. Run the app as a systemd user service

**Run**

```bash
systemctl --user link "$PWD/deploy/systemd/pastebin-app.service"
systemctl --user daemon-reload
systemctl --user enable --now pastebin-app
```

- `link`: makes systemd aware of a unit file that lives outside its usual folders
  (it creates a symlink in `~/.config/systemd/user/`).
- `daemon-reload`: makes systemd re-read unit files. Run it after every edit to one.
- `enable --now`: `enable` starts it at login from now on, and `--now` also starts it now.

**You should see** a line like `Created symlink .../default.target.wants/pastebin-app.service → ...`.

**Check it**

```bash
systemctl --user status pastebin-app          # "active (running)"
journalctl --user -u pastebin-app -n 20       # uvicorn startup lines
ls -l ~/.config/systemd/user/                 # the symlinks systemd made
```

Try the restart policy: `systemctl --user kill --signal=SIGKILL pastebin-app` simulates a crash.
Run `status` again a few seconds later, and it should be running again with a new PID
(because of `Restart=on-failure`). A plain `kill` sends SIGTERM, which systemd counts as a
clean shutdown, so it would *not* restart.

## 5. Use it through Nginx

**Run**

```bash
curl -s localhost:8080/healthz
curl -s -X POST localhost:8080/api/pastes \
  -H 'content-type: application/json' \
  -d '{"content":"hello from the runbook","ttl":"10m"}'
```

**You should see** `{"status":"ok"}`, then JSON with `id`, `url` and `expires_at`.

**Check it**

- Open http://localhost:8080 in a browser, create a paste and open its link.
- `curl -s localhost:8080/api/pastes/<id>` returns the content.
- `docker compose logs nginx | tail` shows your requests in Nginx's access log.
- `journalctl --user -u pastebin-app -n 5` shows the same requests from the app's side.

Every request now goes browser → Nginx (8080) → uvicorn (8000) → Postgres (5442).

## 6. Schedule cleanup with a systemd timer

**Run**

```bash
systemctl --user link "$PWD/deploy/systemd/pastebin-cleanup.service"
systemctl --user link "$PWD/deploy/systemd/pastebin-cleanup.timer"
systemctl --user daemon-reload
systemctl --user enable --now pastebin-cleanup.timer
```

You enable the **timer**, not the service. The timer starts the service.

**Check it**

```bash
systemctl --user list-timers pastebin-cleanup     # NEXT is within the next minute
systemctl --user start pastebin-cleanup           # run it once by hand
journalctl --user -u pastebin-cleanup -n 5        # "cleanup: deleted 0 expired paste(s)"
```

After a couple of minutes, `journalctl --user -u pastebin-cleanup` shows one run per minute.

## 7. Schedule the same job with cron

**Run**

```bash
mkdir -p logs
(crontab -l 2>/dev/null; cat deploy/cron/pastebin-cleanup.cron) | crontab -
crontab -l
```

The first command keeps any cron entries you already have and appends ours.

**You should see** our block, from `# BEGIN pastebin` to `# END pastebin`, with the
`* * * * * cd $HOME/Desktop/pp/pastebin ...` line inside it.

**Check it**: wait up to a minute, then:

```bash
tail -f logs/cleanup-cron.log     # a new line every minute; Ctrl+C to stop
```

Now two schedulers run the same job. It's safe because deleting already-deleted rows
does nothing (see "Expiry has two layers" in architecture.md).

## 8. Watch a paste expire

**Run**

```bash
ID=$(curl -s -X POST localhost:8080/api/pastes -H 'content-type: application/json' \
  -d '{"content":"short-lived","ttl":"1m"}' | python3 -c 'import sys,json; print(json.load(sys.stdin)["id"])')
echo $ID
curl -s -o /dev/null -w '%{http_code}\n' localhost:8080/api/pastes/$ID     # 200
```

Wait just over a minute, then:

```bash
curl -s -o /dev/null -w '%{http_code}\n' localhost:8080/api/pastes/$ID     # 404
```

**Check it**: within the next minute, one of the cleanup runs deletes it:

```bash
journalctl --user -u pastebin-cleanup -n 5 | grep 'deleted 1'
grep 'deleted 1' logs/cleanup-cron.log
```

Only one of the two will have `deleted 1`. Whichever ran first got the row, and the other found nothing.

To watch the two layers separately, disable both schedulers (`systemctl --user stop
pastebin-cleanup.timer`, then comment the line out with `crontab -e`), create a 1-minute
paste and wait. The API returns 404 straight away, while the row is still in the table:

```bash
docker compose exec db psql -U pastebin -c 'select id, expires_at, expires_at <= now() as expired from pastes'
```

## 9. Tear it all down

**Run**

```bash
# cron: delete everything between our BEGIN/END markers, keep anything else
crontab -l | sed '/^# BEGIN pastebin$/,/^# END pastebin$/d' | crontab -

# systemd: stop, disable, and remove the links
systemctl --user disable --now pastebin-cleanup.timer pastebin-app
systemctl --user stop pastebin-cleanup.service
rm -f ~/.config/systemd/user/pastebin-app.service \
      ~/.config/systemd/user/pastebin-cleanup.service \
      ~/.config/systemd/user/pastebin-cleanup.timer
systemctl --user daemon-reload

# containers (add -v to also delete the database volume)
docker compose down
```

**Check it**

```bash
crontab -l | grep pastebin            # nothing
systemctl --user list-units 'pastebin*' --all   # "0 loaded units listed"
docker compose ps                     # empty
```

## Troubleshooting

| Symptom | Look at | Usual cause |
|---|---|---|
| `curl :8080` → 502 | `systemctl --user status pastebin-app` | App not running or crashed. Read its journal. |
| App keeps restarting | `journalctl --user -u pastebin-app -n 50` | Postgres not up yet, or `.env` missing or wrong |
| `curl :8080` → connection refused | `docker compose ps` | Nginx container not running |
| `relation "pastes" does not exist` | `uv run alembic current` | Migration not run (step 3) |
| Cron log never appears | `crontab -l`, `ls logs/` | Missing `logs/` folder, or the cron line wasn't installed |
| Changed a unit file, nothing happened | | Forgot `systemctl --user daemon-reload` and a restart |
| Services stop when you log out | | Expected: no linger (see architecture.md) |
