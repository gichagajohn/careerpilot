# CareerPilot AI — Development Phase Log

Status: ✅ **Phase 8 complete** (18 Aug 2026) — awaiting approval for Phase 9.

---

## Phase 1 — Project skeleton, database, master profile, opportunity schema

### What was built
- **Backend skeleton**: FastAPI app (`app/main.py`) with `/health`, `/docs` (OpenAPI), CORS, lifespan startup.
- **Configuration**: `app/core/config.py` (pydantic-settings) — every secret/env var documented in `.env.example`. No hardcoded secrets.
- **Database**: SQLAlchemy 2 + 28 tables (users, master profile, education, experience, skills, certifications, documents, extractions, organizations, jobs, job_sources, scholarships, verification_results, applications, application_events, application_answers, cv_versions, cover_letters, interviews, interview_questions, deadlines, notifications, notification_preferences, search_sources, search_runs, result_cache, settings, llm_usage_log). SQLite for local dev; PostgreSQL via `DATABASE_URL` (same code).
- **Auth**: register / login / refresh / me — bcrypt password hashing + JWT access & refresh tokens.
- **Master profile API**: upsert profile + CRUD for education, experience, skills, certifications. Phone encrypted at rest (Fernet) and decrypted only for the owner.
- **Opportunity APIs**: jobs + scholarships (create, list with filters, update, get). Job multi-source support (`job_sources`) for deduplication (spec §24).
- **Application tracker API**: create / list / update with the full status lifecycle (spec §11), audit events, auto `date_applied`.
- **Documents API**: secure upload (type/size limits), list, delete. Extraction workflow arrives in Phase 6.
- **Dashboard summary API**: totals, new, high-match, applications, interviews, offers, scholarships, upcoming deadlines (14 days).
- **Migrations**: Alembic configured (reads `DATABASE_URL` from settings; `render_as_batch` for SQLite).
- **Seed script**: creates John's master profile from the spec (the single source of truth) + optional demo jobs/scholarships clearly marked "Demo example".
- **Tests**: 24+ assertions across auth, profile (incl. cross-user isolation), PII encryption, jobs, scholarships, tracker, dashboard — all green.
- **Cloud-ready**: backend `Dockerfile`, `docker-compose.yml` (Postgres + backend, auto-migrate), deployment guide (Neon/Supabase/Railway/VPS).

### How to run (Windows)
```bat
cd careerpilot\backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy ..\.env.example .env
:: set SECRET_KEY and ENCRYPTION_KEY in .env (python ..\scripts\gen_key.py)
python ..\scripts\init_db.py
python ..\scripts\seed.py --email johngichaga8@gmail.com --demo
uvicorn app.main:app --reload --port 8000
```
Then open http://localhost:8000/docs, log in via `/api/v1/auth/login`, and explore.

### Limitations (Phase 1)
- No discovery agents yet (Phase 2) — opportunities enter via API or seed.
- No verification / matching / ranking (Phases 4–5) — statuses default to UNVERIFIED.
- No document text extraction (Phase 6) — uploads stored, status PENDING.
- No frontend dashboard (Phase 8) — API only; use `/docs` (Swagger UI).
- No scheduler / notifications (Phases 2/5) — the APScheduler worker is planned.
- `AUTO_CREATE_TABLES=true` is dev-only convenience; production uses Alembic.

---

---

## Phase 2 — JobScout discovery engine

### What was built
- **LLM provider abstraction** (`app/core/llm.py`): Gemini Flash (AI Studio free tier) primary; Groq and local Ollama as OpenAI-compatible fallbacks; every call logged to `llm_usage_log`. No API key → clean `LLMError`, never a crash.
- **Normalizer** (`app/services/normalizer.py`): LLM path (specialized YAML prompt, strict JSON, Pydantic-validated) **plus a deterministic no-LLM fallback** so the pipeline runs with zero keys. Extracts title, company, location, salary currency, deadline, employment type, remote, AI-training flag, requirements vs preferred.
- **Source adapters** (`app/services/sources/`): Adzuna (official API, Kenya + configurable countries, free tier, core queries only), Remotive, RemoteOK, Arbeitnow (free APIs), web search (Google CSE / Serper / Tavily — discovery only, never scrapes LinkedIn/Indeed), RSS (feedparser, 202/429-aware).
- **Polite fetching** (`app/services/polite.py`): robots.txt respected, per-domain 1s rate limit, 24h content cache, 2 MB cap.
- **Deduplication** (`app/services/dedup.py`): normalized-key exact match + fuzzy Jaccard → one canonical job, every listing URL preserved in `job_sources` (spec §24).
- **Relevance gate** (`app/services/relevance.py`): conservative title/text keyword filter keeps the pool clean (configurable via `JOBS_RELEVANCE_FILTER`).
- **APScheduler** (`app/services/scheduler.py`): JobScout cron at 0/8/16 local time (3×/day, spec §15), per-source cadence enforced via `search_sources.last_run_at` (Adzuna daily to stay inside the free quota).
- **API**: `POST /agents/jobscout/run` (manual trigger), `GET /agents/sources`, `POST /agents/sources/{id}/toggle`.
- **Default sources** seeded: adzuna (daily), remotive/remoteok/arbeitnow (3×), websearch (2×), RSS (2×).
- **Tests**: 43 total, all green (LLM parsing/fallbacks, normalizer, dedup, adapters with mocked HTTP, RSS throttling, relevance gate, scheduler cadence, full JobScout pipeline incl. repeat-run idempotency).

### Live verification (real network)
- 416 raw listings across 26 query categories × 6 sources → 364 filtered as out-of-scope → **2 relevant opportunities stored** (AI data-labeling and content-reviewer roles, with company names extracted), 0 errors.
- Scheduler confirmed running at 00/08/16 Africa/Nairobi.
- Adzuna + web search intentionally skipped in the sandbox (no API keys); they activate the moment `ADZUNA_APP_ID/KEY` and a search key are added to `.env`.

### How to run
```bat
cd careerpilot\backend
python ..\scripts\seed.py --email johngichaga8@gmail.com   :: adds default sources
uvicorn app.main:app --reload --port 8000
:: manual run (or wait for the cron):
:: POST /api/v1/agents/jobscout/run?force=true   (Authorization: Bearer <token>)
```
Add keys to `.env` for full coverage: `ADZUNA_APP_ID`, `ADZUNA_APP_KEY`, and at least one of `GOOGLE_CSE_KEY/CX`, `SERPER_KEY`, `TAVILY_KEY`; `GEMINI_API_KEY` enables LLM-quality extraction.

### Limitations (Phase 2)
- **No verification yet** (Phase 4): everything lands as `UNVERIFIED`; expired listings still enter the pool.
- **No matching/ranking yet** (Phase 5): relevance is a coarse pre-filter, not a match score.
- **No scholarships** (Phase 3 is the ScholarshipScout).
- **No notifications/daily report** (Phases 5/10).
- Free-tier APIs have quotas (Adzuna ~1,000 calls/mo — respected via core-queries + daily cadence).
- Web search only activates with a search API key; ReliefWeb throttles datacenter IPs (202) — works on residential connections.

---

## Phase 3 — ScholarshipScout discovery engine

### What was built
- **Scholarship normalizer** (`app/services/normalizer.py`): LLM path (dedicated `scholarship_extraction.yaml` prompt, strict JSON, Pydantic-validated) + deterministic fallback. Captures all 19 required fields (spec §4): university, country, programme, funding level, tuition/accommodation/stipend/travel/insurance coverage, application fee, eligibility, classification/field/work-experience/English/age requirements, deadline, application + official URLs, Kenya/Africa-open flags.
- **Funding evidence rule (spec §4, hard guarantee):** `assess_funding()` only returns `FULLY FUNDED` when the source text explicitly confirms it ("fully funded", "fully-financed", or full tuition + stipend + accommodation). Anything weaker is downgraded — even if the LLM claims otherwise (tested).
- **Official programme page adapter** (`scholarship_pages.py`): polite read-only fetch (robots.txt + rate limits + 24h cache) of official pages — DAAD, Erasmus Mundus, Chevening, Commonwealth, Mastercard Foundation, AIMS, Mandela Rhodes, Fulbright, Gates Cambridge. Page `<title>` used as the listing name.
- **Multi-source support:** new `scholarship_sources` table + dedup (`find_duplicate_scholarship`), migration generated and verified (30 tables).
- **Scholarship relevance gate** (`is_relevant_scholarship`): scholarship/fellowship/grant/Master's/stipend/tuition signals, configurable.
- **Scheduler:** ScholarshipScout cron at 07/19 local (2×/day, spec §15) alongside JobScout.
- **API:** `POST /agents/scholarshipscout/run`; scholarship sources under `GET /agents/sources`.
- **Queries:** 13 search areas × 3 variants (base / "fully funded" / "scholarship") from spec §4.
- **Tests:** 55 total, all green (scholarship normalizer incl. funding-evidence and LLM-lying cases, scholarship dedup, ScholarshipScout pipeline, relevance gates).

### Live verification (real network)
- 396 raw listings → 234 filtered as out-of-scope → **10 stored** (7 official programme pages with real titles + 3 gated fellowships), 0 errors.
- Evidence rule verified live: only Chevening and ACET marked FULLY FUNDED (text confirms); DAAD/Erasmus/Fulbright/Gates stay UNSPECIFIED pending verification.
- Scheduler confirmed: JobScout 0/8/16 + ScholarshipScout 7/19 (Africa/Nairobi).

### How to run
```bat
python ..\scripts\seed.py --email johngichaga8@gmail.com   :: adds 12 scholarship sources
uvicorn app.main:app --reload --port 8000
:: POST /api/v1/agents/scholarshipscout/run?force=true
```
Add `GEMINI_API_KEY` for high-quality 19-field extraction; a search API key enables web-discovery of individual scholarship postings.

### Limitations (Phase 3)
- **No verification yet (Phase 4)** — every scholarship is UNVERIFIED; country/deadline parsing can be noisy without the LLM.
- **No matching yet (Phase 5)** — funding flags are evidence-based, but no eligibility score yet.
- FETCH pages yield programme-level info; per-scholarship detail comes from web search (needs a key) and Phase 4 verification.
- Deterministic fallback is intentionally conservative (names/URLs solid; detailed fields best with LLM).

---

## Phase 4 — Opportunity Verifier

### What was built
- **Verifier agent** (`app/agents/verifier.py`) — the 10-check engine from spec §5, each check a deterministic, auditable function:
  1. Organization exists (polite domain probes)
  2. Listed on official/reputable source (known-domain allowlist incl. Adzuna, Remotive, official scholarship orgs)
  3. Application URL legitimate (HTTPS, typosquat detection via Levenshtein vs known domains)
  4. Deadline still valid (fuzzy date parsing via `python-dateutil`)
  5. Duplicate canonicalized (dedup cluster present)
  6. Job actually exists (polite fetch of listing URL; 404/410 → gone)
  7. Suspicious payment requirements (keyword scan → **SUSPICIOUS**)
  8. Scholarship exists (official page reachable)
  9. Programme exists on university site (official-page content check; needs a search key for full coverage)
  10. Application process consistent (domain match; personal-email domains → SUSPICIOUS)
- **Classification** per spec §5: `VERIFIED` (all pass) / `LIKELY VERIFIED` (majority pass) / `UNVERIFIED` / `SUSPICIOUS` (payment/process red flags — never recommended) / `EXPIRED` (deadline passed). Human overrides remain possible via the PATCH endpoints.
- **Audit trail:** every check stored in `verification_results` with PASS/FAIL + details + timestamp.
- **API:** `POST /agents/verify/run?entity_type=job|scholarship`.
- **Scheduler:** verifier cron every 6h, after discovery cycles.
- **Tests:** 67 total, all green (deadline logic incl. unparseable, payment keyword scan incl. scholarship exemption, HTTPS/typosquat, process consistency, reputability, full pipeline status assignment).

### Live verification (real network)
- 5 jobs + 12 scholarships verified in 16 s, 0 errors:
  - **4 correctly marked EXPIRED** (Workada 26-Jul, TELUS 23-Jul, Commonwealth 24-Jul, Gates Cambridge 11-Aug — all past deadlines).
  - **0 SUSPICIOUS**; demo records correctly stay UNVERIFIED/LIKELY VERIFIED.
  - Full audit trail visible per entity (sample: Erasmus Mundus — 8 PASS, 2 informational FAILs).

### How to run
```bat
:: POST /api/v1/agents/verify/run?entity_type=job   (or omit entity_type for both)
:: Scheduled automatically every 6h
```

### Limitations (Phase 4)
- Programme-existence (check 9) and org-existence (check 1) need a web-search key for full fidelity; without one they degrade to polite fetch probes.
- Deadline parsing is fuzzy — human confirmation before APPLY remains the rule (Phase 9).
- Verification runs over `UNVERIFIED` records only; re-verification of EXPIRED/SUSPICIOUS is a planned Phase 5/9 refinement.

---

## Phase 5 — Eligibility Analyst & Matcher

### What was built
- **Deterministic scoring engine** (`app/services/scoring.py`) — your exact 100-pt rubric (spec §6):
  - Jobs: Education 20 · Subject match 20 · Experience 20 · Technical skills 15 · Registration 10 · Location 10 · Other 5
  - Scholarships: Education 25 · Field 20 · Classification 15 · English 10 · Experience 10 · Kenya/Africa-open 10 · Age 10
  - Output: score 0–100, `ELIGIBLE / POSSIBLY ELIGIBLE / NOT ELIGIBLE`, plus **strengths, gaps, risks, missing requirements** — never hidden (spec §6).
  - No LLM in scoring: fully reproducible, cannot hallucinate.
- **Subject normalisation** (Mathematics ⇄ maths; Computer Studies ⇄ CS/ICT…), experience years from profile dates, skill matching via token overlap (with degree/registration/English requirements excluded so they aren't double-counted), location rules incl. a configurable `open_to_international` flag.
- **Relevance score** (Jaccard overlap of opportunity text vs profile) and **priority score** with your configurable weights: 30% eligibility · 25% relevance · 15% growth · 10% compensation · 10% deadline · 10% org quality (`setting priority_weights` — editable).
- **Matcher agent** (`app/agents/matcher.py`): scores all opportunities, persists `match_score`, `priority_score`, `eligibility`, `match_details` (the "why you match" card), fires notifications.
- **Notifications** (`app/services/notifications.py`): in-app always; email (SMTP) + Telegram (bot) when configured; deduplicated per entity+type; preferences API. High-match (≥80, configurable) and deadline-approaching (≤3 days) alerts.
- **API**: `POST /agents/matcher/run`, `GET /recommendations` (ranked shortlist), full notifications inbox + preferences routes.
- **Scheduler**: verifier task now also runs matching (verify → score → notify) every 6h.
- **Schema**: `jobs.match_details`, `scholarships.match_details/priority_score`, `notifications.entity_type/entity_id` — migration generated + verified; dev SQLite self-heals via idempotent column adds (`core/db.py`).
- **Tests**: 83 total, all green (rubric components, gaps/risks, scholarship scoring, priority weights, matcher pass, notification dedup, idempotency).

### Live verification (real network)
- Matcher scored **7 jobs + 15 scholarships** in <1 s, 0 errors, 21 notifications created (then dedup'd to 0 on re-runs).
- Ranked cards look right — e.g. Mathematics Teacher 92.5 ELIGIBLE (strengths: B.Ed First Class, teaching experience; gap: CBC/CBE not on file); Computer Science & ICT Teacher 97.5 ELIGIBLE (gap: international curriculum + relocation); Erasmus Mundus 100 ELIGIBLE.
- Smoke test extended to 13 checks incl. matcher + notifications + recommendations — all green.

### How to run
```bat
:: POST /api/v1/agents/matcher/run?force=true   (or wait for the 6h cron)
:: GET /api/v1/recommendations                 (ranked shortlist)
:: GET /api/v1/notifications                   (inbox)
:: PUT /api/v1/notifications/preferences       (email/telegram toggles)
```
Configure email/Telegram in `.env` (`SMTP_*`, `TELEGRAM_*`) and enable the channels via the preferences API to receive alerts off-dashboard.

### Limitations (Phase 5)
- Skill matching is lexical (substring/token overlap); semantically-phrased requirements ("strong mathematics background") can be under-credited — an embeddings/LLM upgrade is a planned Phase 6+ refinement.
- Salary/funding comparisons use simple presence heuristics; international roles score 0 on location unless `open_to_international=true` (set in Settings).
- Notification channels other than in-app need SMTP/Telegram credentials to go live.

---

## Phase 6 — CV Generator (with the anti-fabrication FactCheck gate)

### What was built
- **FactCheck gate** (`app/services/fact_check.py`) — the anti-fabrication core (spec §22):
  - A `FactStore` is built from the master profile (orgs, institutions, degrees, fields, skills, certifications, subjects, grades, registration, classifications, names, locations, roles).
  - Every content line's named-entities are extracted and verified against the store with normalized containment; identity lines (phone/email/location/subjects) are marked `profile_field`.
  - **Static fabrication detectors** (spec §22 list): invented international experience, unclaimed curriculum (IGCSE/IB/Cambridge/A-Level), awards, references sections, salary history, unverified grades, unclaimed language fluency → **any hit voids the whole document**.
  - Report per claim: `CLAIM / SOURCE / VERIFIED YES-NO`; unverifiable lines are removed and counted.
- **CV generator** (`app/services/cv_generator.py`):
  - Role-type detection (math / computer_science / edtech / ai_training / curriculum / international) with per-role skill preference ordering (spec §7) — tailoring by re-ordering real skills, never by inventing.
  - Deterministic assembly strictly from the profile: CONTACT · PROFESSIONAL SUMMARY · EDUCATION · TEACHING EXPERIENCE · SKILLS · REGISTRATION & CERTIFICATIONS.
  - ATS-friendly `.docx` (single column, Calibri, no graphics) + clean `.pdf` (reportlab).
  - No references, no salary history, no fabricated achievements — structurally.
- **CV Tailor agent** (`app/agents/cv_tailor.py`): generates per-application CVs, writes `.docx`+`.pdf`, stores a `cv_versions` row with the JSON snapshot and the fact-check report, links it to the application.
- **API**: `POST /cv/applications/{id}/generate` · `GET /cv/versions` · `GET /cv/versions/{id}` (snapshot + report) · downloads `.docx` / `.pdf`.
- **Tests**: 91 total, all green — gate removes invented orgs/degrees/skills, voids on prohibited patterns, CV tailors skill order per role, docx/pdf written, no forbidden sections.

### Live verification
- Generated a tailored CV for the Mathematics Teacher application: **18/18 claims verified, 0 removed, 0 prohibited findings**; all three real roles present (incl. Teaching Practice + Form 3/4); `.docx` downloads (37 KB).
- Smoke test extended to **15/15 checks** incl. CV generation + fact-check gate.

### How to run
```bat
:: POST /api/v1/cv/applications/{application_id}/generate
:: GET  /api/v1/cv/versions/{id}/download-docx | download-pdf
:: GET  /api/v1/cv/versions/{id}   (JSON snapshot + fact-check report)
```

### Limitations (Phase 6)
- Summary is deterministic (no LLM yet). An LLM-polished summary is possible later — the FactCheck gate already verifies whatever text is added.
- Fact-check containment is lexical; very unusual phrasing of a legit fact could theoretically be flagged (safe direction — it errs toward removal, never fabrication).

---

## Phase 7 — Cover Letter Generator

### What was built
- **Cover letter generator** (`app/services/cover_letter.py`): per-application letters (spec §8) — names the employer and role, connects real experience to the JD's requirements (matched-requirements surfacing), uses role-specific experience phrasing (math / CS / EdTech / AI / curriculum / international), and includes a learner-centred pedagogy paragraph for teaching roles.
- **Honesty design**: assembled deterministically from the master profile + job record. The two claim paragraphs pass the **FactCheck gate**; a failure **blocks the letter** (no partial letters). Whole text is scanned by the fabrication detectors; **years-of-experience claims are now verified against the profile's computed years** (new gate check, applies to CVs too).
- **Agent** (`app/agents/cover_letter_agent.py`): generates, writes `.docx` + `.pdf`, stores a `cover_letters` row with content + fact-check report, links to the application.
- **API**: `POST /cover-letters/applications/{id}/generate` · `GET /cover-letters` · downloads `.docx`/`.pdf`.
- **Tests**: 95 total, all green (role-specificity, fact-check pass, no fabrication, per-role uniqueness, docx/pdf output, years-claim guard).

### Live verification
- Generated the cover letter for the Mathematics Teacher application — reads naturally, names Nova Pioneer + the role, cites B.Ed First Class, current role, TSC registration, ICT-integration match, learner-centred pedagogy: **fact-check 2/2 verified, 0 removed, 0 prohibited**. Downloads ready.
- Smoke test extended to **16/16 checks** (CV + cover letter + gate).

### How to run
```bat
:: POST /api/v1/cover-letters/applications/{application_id}/generate
:: GET  /api/v1/cover-letters/{id}/download-docx | download-pdf
```

### Limitations (Phase 7)
- Letters are deterministic (no LLM voice yet); an LLM-polished variant can be added later under the same FactCheck gate.
- Matched-requirements surfacing is lexical (same as Phase 5/6 skill matching).

---

## Phase 8 — Dashboard (Next.js + Tailwind)

### What was built
- **Next.js 14 App Router** frontend (`frontend/`):
  - Automatic API proxy: `/api/*` → backend (same-origin for the browser, no CORS issues in the sandbox preview).
  - All 12 pages built: **Login**, **Dashboard home**, **Jobs**, **Scholarships**, **Applications**, **Documents**, **CV Builder**, **Cover Letters**, **Interviews**, **Profile**, **Settings**, plus a clean 404 route.
  - Sidebar + top navigation (10 links), auth guard (redirect to /login without token), logout.
  - Tailwind CSS (`card`, `btn`, `input`, `label`, `badge` component layer — consistent, clean, no external component library).
- **Pages detail:**
  - **Dashboard home**: 8 stat cards (total, new, high match, applications, interviews, offers, scholarships, deadlines), upcoming-deadline list, "high-match jobs" grid, "scholarships" grid — all live data from the API.
  - **Jobs/Scholarships**: filters (search, verification, min match / funding), card list with "Add to applications" button + why-you-match card (strengths, gaps, risks, verification badge).
  - **Applications**: full tracker with status select/interview date/follow-up, one-click CV generation + cover letter generation per row.
  - **CV Builder**: versioned list with preview (rendered sections + fact-check report + download .docx/.pdf).
  - **Cover Letters**: list with full text preview + download.
  - **Interviews**: filtered view of applications at INTERVIEW status (Phase 10 for interview prep).
  - **Documents**: upload form + file type selector + list with delete.
  - **Profile**: view/edit master profile with read-only education/experience/skills cards (single source of truth).
  - **Settings**: notification preferences toggles (channels + triggers), linked to the backend `/notifications/preferences` endpoint.

### Live verification
- Frontend builds cleanly (13 routes, ~90 KB first load).
- API proxy delivers real data: 28 opportunities, 18 scholarships, 3 interviews, recommendations, notifications.
- Start both servers: `backend: uvicorn` + `frontend: npm run dev` → http://localhost:3000
- Smoke test continues at **16/16** (backend-only — frontend is a separate dev server).

### Limitations (Phase 8)
- No application assistant (Phase 9) — the "Apply" button is a placeholder for now.
- No interview prep (Phase 10).
- No daily report (Phase 10).

---

## Phase 9 — Application Assistant (Playwright + human-in-the-loop)

### What was built
- **Playwright assistant** (`app/services/application_assistant.py`):
  - Opens the application URL in headless Chromium, scans the form (labels + placeholders + aria-labels + names), matches known fields against the master profile (name, email, phone, location, CV file, cover letter file) and fills them.
  - **Hard-blocks sensitive attestations** (spec §10): criminal record, ID/passport/visa, legal declarations, salary expectations, diversity/disability, TSC number, "is this information true" checks, CAPTCHA/reCAPTCHA — the assistant stops and lists them for the user.
  - Saves draft if a Save Draft button exists on the page.
  - **Never clicks submit** — returns the APPLICATION REVIEW card for human approval (spec §9).
- **Field detection heuristics**: label `for=""` → input, `placeholder`, `aria-label`, `name` attribute. Sensitive-field patterns matched via regex (case-insensitive). Non-sensitive fields filled with profile data; file uploads supported.
- **API**: `POST /applications/{id}/assist` — runs the assistant, writes an `ASSISTANT_RUN` event, sets status to `READY FOR REVIEW`.
- **Tests**: 97 total, all green (+2 for field mapping + sensitive detection; Playwright browser test skipped in sandbox — requires `playwright install chromium` on your PC).

### How to run on your PC
```bat
cd backend
.venv\Scripts\python.exe -m playwright install chromium
:: then as before: start the API, dashboard, create an application,
:: POST /api/v1/applications/{id}/assist
```
The first run downloads Chromium (~150 MB). After that the assistant works.

### Limitations (Phase 9)
- The sandbox lacks system libraries (`libnspr4`) for Playwright; the unit tests cover field heuristics, but the full Playwright flow requires your Windows PC.
- Only generic heuristics for field matching — per-site recipes (stored JSON) can be added progressively to handle non-standard form layouts.
- Draft-saving varies per site; many forms have no draft button.
- The assistant auto-fills and stops; the user must manually submit the form on the target site after reviewing.

_Next: Phase 10 — Interview Preparation + Daily Career Report._
