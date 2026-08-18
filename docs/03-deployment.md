# CareerPilot AI — Deployment Guide (Phase 1: backend only)

You approved **early cloud**. The Phase 1 codebase is ready for it: the same
SQLAlchemy models run on SQLite (local) or PostgreSQL (cloud); Alembic manages
schema; secrets come from environment variables.

> Full production hardening (frontend deploy, HTTPS, backups, Playwright
> worker, notifications) arrives in later phases. This guide gets the API
> running 24/7 for ~$0 so the scheduler (Phase 2+) can work while you sleep.

---

## Option A — Free managed Postgres (Neon or Supabase)

1. Create a free account at **neon.tech** (or supabase.com).
2. Create a database; copy the connection string, e.g.
   `postgresql://user:pass@ep-xxx.region.aws.neon.tech/careerpilot?sslmode=require`
3. Put it in your `.env` as `DATABASE_URL`.

## Option B — Railway (free-ish, simple)

1. Create an account at **railway.app**; create a new project.
2. Add a **PostgreSQL** service (free tier) and a **Service** from GitHub repo.
3. Set the service start command: `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000`
4. Set environment variables (Service → Variables):
   - `DATABASE_URL` (from the Railway Postgres service, `${{ Postgres.DATABASE_URL }}`)
   - `SECRET_KEY`, `ENCRYPTION_KEY`, `AUTO_CREATE_TABLES=false`
5. Backend `Dockerfile` is included; Railway will use it.

## Option C — Self-hosted VPS (€4–7/mo, full control)

1. Rent a Hetzner CX22 (or similar) with Docker installed.
2. `git clone` your repo on the server.
3. `export SECRET_KEY=... ENCRYPTION_KEY=...`
4. `docker compose up --build -d` → Postgres + backend on port 8000.
5. Add Caddy (or nginx) for HTTPS reverse proxy.

---

## Always

- Run `alembic upgrade head` before starting the API (the Docker image does this automatically).
- Never commit `.env`. Add real secrets through your platform's variable UI or shell.
- Generate `ENCRYPTION_KEY` with `python scripts/gen_key.py`.
- Verify: `curl https://<your-host>/health` → `{"status":"ok",...}`

## Local ↔ cloud

The same `DATABASE_URL` env var switches environments — no code changes.
Local: `sqlite:///./data/careerpilot.db` · Cloud: `postgresql+psycopg://...`
