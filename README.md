# CareerPilot AI

Personal AI Career & Scholarship agent — discovers teaching jobs, AI-training
opportunities and fully-funded Master's scholarships; verifies them; scores
them against one verified master profile; prepares fact-checked CVs and cover
letters; assists applications **with human-in-the-loop approval**; and tracks
everything through to interview prep.

## Status

✅ **Phase 1 complete** — skeleton, database, auth, master profile, opportunities, tracker, docs API.
✅ **Phase 2 complete** — JobScout: 6 source adapters (Adzuna/Kenya, Remotive, RemoteOK, Arbeitnow, web search, RSS), LLM normalizer w/ deterministic fallback, dedup, polite fetching, relevance gate, APScheduler cron (3×/day).
✅ **Phase 3 complete** — ScholarshipScout: 19-field capture, official-page adapter (DAAD, Erasmus+, Chevening, Commonwealth, Mastercard…), strict "fully funded only with official evidence" rule, scholarship dedup + sources, 2×/day cron.
✅ **Phase 4 complete** — Verifier: 10-check engine (spec §5), statuses VERIFIED/LIKELY VERIFIED/UNVERIFIED/SUSPICIOUS/EXPIRED, audit trail, every-6h cron.
✅ **Phase 5 complete** — Eligibility Analyst & Matcher: 100-pt rubric (spec §6), ELIGIBLE/POSSIBLY/NOT + strengths/gaps/risks, configurable priority weights (spec §23), ranked recommendations, notifications (in-app + email + Telegram).
✅ **Phase 6 complete** — CV Generator with the **FactCheck gate** (spec §22): every claim traced to the master profile, unverifiable claims removed, fabrication detectors void the document, ATS-friendly `.docx` + `.pdf`, versioned storage.
✅ **Phase 7 complete** — Cover Letter Generator.
✅ **Phase 8 complete** — Next.js + Tailwind Dashboard: 12 pages, live API proxy.
✅ **Phase 9 complete** — Application Assistant: Playwright auto-fill + sensitive-field hard blocks + human-in-the-loop review gate (spec §9–10).
⏭ Awaiting approval to begin **Phase 10 (Interview Preparation + Daily Report)**.

See [docs/02-phases.md](docs/02-phases.md) for the phase log and
[docs/01-architecture-proposal.md](docs/01-architecture-proposal.md) for the approved architecture.

## Quick start (Windows, backend only)

```bat
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python ..\scripts\gen_key.py          :: put ENCRYPTION_KEY into .env
copy ..\.env.example .env             :: fill SECRET_KEY / ENCRYPTION_KEY
python ..\scripts\init_db.py
python ..\scripts\seed.py --email johngichaga8@gmail.com --demo
uvicorn app.main:app --reload --port 8000
```

- API docs (Swagger UI): http://localhost:8000/docs
- Health check: http://localhost:8000/health

## Testing on Windows (Phases 1–4)

### One-command option
```bat
:: from the careerpilot/ folder
scripts\test_all.bat
```
Runs everything: installs deps → `pytest` (67 unit tests) → starts the API → runs the
end-to-end smoke test (`scripts\smoke_test.py`, 13 checks) → stops the API.

### Step-by-step option
```bat
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python ..\scripts\init_db.py
python ..\scripts\seed.py --email johngichaga8@gmail.com --demo
python -m pytest -q                      :: 1) unit tests (67 expected)
python -m uvicorn app.main:app --reload --port 8000
```
Then in another terminal:
```bat
cd backend
.venv\Scripts\activate
python ..\scripts\smoke_test.py           :: 2) API smoke test (10 quick checks)
python ..\scripts\smoke_test.py --full   :: 3) + live discovery & verification (13 checks)
```

### Manual testing via Swagger UI
Open http://localhost:8000/docs while the server runs. Try, in order:
1. `POST /auth/login` → copy `access_token` → click **Authorize** → paste it.
2. `GET /auth/me` · `GET /profile` (your seeded master profile).
3. `POST /jobs` (create a test job) · `PATCH /jobs/{id}` (set `verification_status`).
4. `POST /scholarships` · `GET /scholarships`.
5. `POST /applications` → `PATCH` status to `INTERVIEW`.
6. `GET /dashboard/summary`.
7. `POST /agents/jobscout/run?force=true` · `POST /agents/scholarshipscout/run?force=true` · `POST /agents/verify/run` — watch real discoveries land and get verified.

### Optional: enable live sources
Edit `backend/.env` and add any of: `GEMINI_API_KEY` (LLM extraction),
`ADZUNA_APP_ID` + `ADZUNA_APP_KEY` (Kenya jobs), and one of
`GOOGLE_CSE_KEY/CX`, `SERPER_KEY`, `TAVILY_KEY` (web discovery + verification).
Without keys, the pipeline still runs on the free APIs (Remotive, RemoteOK,
Arbeitnow, RSS, official scholarship pages) and the deterministic extractor.

Login after seeding: `johngichaga8@gmail.com` / `ChangeMe123!` (change it).

## Project map

```
backend/app/        FastAPI application (core, models, schemas, api, agents/* later)
backend/alembic/    Database migrations
scripts/            init_db, gen_key, seed, (run_dev later)
docs/               Architecture, phase log, deployment guide
docker-compose.yml  PostgreSQL + backend (cloud-style local stack)
```

## Safety principles

- The master profile is the **only** source of facts; fabricated claims are rejected by the FactCheck gate (Phase 6).
- The application assistant **never submits without explicit approval** and never guesses on sensitive fields (Phases 9–10).
- Secrets live only in `.env` / platform variables — never in the repo.
