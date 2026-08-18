# CareerPilot AI — Architecture Proposal (Phase 0)

| | |
|---|---|
| **Project** | CareerPilot AI — personal AI Career & Scholarship Agent |
| **Author** | John Gichaga (with AI engineering assistance) |
| **Date** | 18 August 2026 |
| **Status** | ⏸ Awaiting approval before Phase 1 |
| **Scope** | Architecture, schema, folder structure, agent design, phases, tooling, costs. No implementation code yet. |

---

## 0. Executive Summary

CareerPilot AI is a **single-user, human-in-the-loop career automation platform**. It continuously discovers teaching jobs, AI-training opportunities, and Master's scholarships; verifies them; scores them against one canonical master profile; prepares tailored, fact-checked CVs and cover letters; assists with applications **but never submits without explicit human approval**; and tracks everything through to interview prep.

The recommended architecture is a **modular monolith**:

- **Backend:** Python + FastAPI + SQLAlchemy, with an in-process scheduler (APScheduler) — no Celery/Redis needed at personal scale.
- **Agents:** 8 specialized agents (discovery → verification → eligibility → tailoring → generation → application → interview) orchestrated through the database and a task queue, each with its own specialized prompt stored in YAML.
- **Frontend:** Next.js (App Router) + Tailwind CSS dashboard consuming a FastAPI REST API.
- **Database:** SQLite for local Windows development, PostgreSQL (Neon/Supabase free tier) for production — same code via SQLAlchemy.
- **LLM:** Provider-agnostic layer with a **free-first default** (Gemini Flash via Google AI Studio, ~1,500 req/day free; fallback Groq; optional local Ollama; paid upgrade path to OpenAI/Anthropic).
- **Anti-fabrication:** A mandatory **FactCheck gate** runs before any CV, cover letter, or application answer is finalized. Every factual claim must trace to a verified entry in the master profile; anything unverifiable is removed. Fabrication is structurally impossible, not just discouraged.
- **Automation:** Playwright "assist mode" fills forms and saves drafts, then stops for an `APPLY / EDIT / CANCEL` review gate. Sensitive attestations (criminal record, identity, salary, legal declarations, etc.) always require human input.

**Estimated operating cost: $0–10/month** (free tiers cover everything; the ceiling assumes optional paid LLM/cloud tiers).

---

## 1. Specification Analysis → Key Design Decisions

The spec is a pipeline: *Internet → Discovery → Verification → Eligibility → Matching → Ranking → CV Tailoring → Cover Letter → Application Prep → Human Review → Submission → Tracking → Interview Prep → Follow-up.* Each arrow is a component. The design decisions below resolve the important tensions in the spec.

| Spec requirement | Design decision | Rationale |
|---|---|---|
| Modular multi-agent system | **Modular monolith**, not microservices | Single user, low volume. One FastAPI app + scheduler + agent modules keeps ops trivial (one `uvicorn` process) while preserving clean agent boundaries. |
| "Do not aggressively scrape" | **API-first, RSS-second, polite HTTP/Playwright-third** source adapters; caching + dedup; configurable cadence (jobs 3×/day, scholarships 2×/day, high-priority 1×/day) | Respects ToS, robots.txt, rate limits; free APIs cover most needs. |
| LLM AI with configurable provider | **Provider abstraction** (`LLMProvider` interface) with Gemini Flash default, Groq fallback, Ollama option, OpenAI/Anthropic paid upgrade | Lock-in prevention; free-first cost model. |
| Anti-fabrication "extremely important" | **Master profile = single source of truth.** Every generation passes a **FactCheck gate**: LLM-draft → claim extraction → claim-vs-profile verification → unverifiable claims deleted → static blocklist check → human review. | Fabrication becomes a pipeline rejection, not a policy. |
| Human-in-the-loop before submission | Application assistant always stops at the review gate; sensitive fields hard-blocked from auto-fill | Spec items 9 & 10 are non-negotiable. |
| Verification | Deterministic rule engine (10 checks) + LLM only for explanation; human override with audit log | Deterministic = auditable, cheap, no hallucination. |
| Scoring | Deterministic weighted rubric (Python), LLM produces only qualitative "why you match" text | Transparent, reproducible, testable. |
| Duplicate detection | Normalized key + fuzzy similarity → one canonical record, many `job_sources` rows | Spec item 24. |
| PostgreSQL production / SQLite dev | SQLAlchemy 2 with a `DATABASE_URL` env switch | Zero code change between dev and prod. |
| "No placeholder functions" | Each phase ships working code + tests; anything deferred is explicitly labeled **PLANNED** in docs | Per spec item 26. |
| Job search API vs scraping | Adzuna (free, includes Kenya), Remotive, RemoteOK, Arbeitnow, USAJOBS, ATS feeds (Greenhouse/Lever/Ashby) + Google CSE search API + RSS. No LinkedIn/Indeed scraping (ToS) — search-snippet discovery only | Compliance + cost. |

**Why not serverless?** Playwright needs a persistent browser runtime; scholarship/job extraction needs background scheduling. A small always-on container (or local process) is simpler and cheaper than serverless orchestration at this scale.

---

## 2. Recommended Architecture

### 2.1 Runtime processes (local dev)

```
┌────────────────────────────────────────────────────────────────┐
│  PROCESS 1 — FastAPI (uvicorn, port 8000)                       │
│   • REST API for the dashboard (auth, CRUD, actions)             │
│   • APScheduler embedded: cron jobs for discovery, verification,  │
│     notifications, daily report                                  │
└────────────────────────────────────────────────────────────────┘
┌────────────────────────────────────────────────────────────────┐
│  PROCESS 2 — Next.js dev server (port 3000)                     │
│   • Dashboard UI (Tailwind), calls FastAPI via /api proxy        │
└────────────────────────────────────────────────────────────────┘
┌────────────────────────────────────────────────────────────────┐
│  PROCESS 3 — (on demand) Playwright browser worker               │
│   • Started per application-assist task; closed after            │
└────────────────────────────────────────────────────────────────┘
```

### 2.2 Data flow / pipeline

```
                     SCHEDULER (APScheduler cron)
        jobs 3×/day · scholarships 2×/day · verify 2×/day · daily report 06:30

        ┌───────────────────────┬────────────────────────┐
        ▼                       ▼                        ▼
  AGENT 1 JobScout      AGENT 2 ScholarshipScout   Source adapters
  (queries × 25         (queries × 12             (API / RSS / polite
   search categories)    search areas)              fetch / search API)
        └───────────┬───────────┘                        │
                    ▼                                    ▼
        ┌─────────────────────┐   raw items      ┌──────────────┐
        │ Normalizer (LLM)    │ ◄───────────────►│ Result cache │
        │ → structured JSON   │   (dedup)        │ + hash       │
        └─────────┬───────────┘                  └──────────────┘
                  ▼
        ┌─────────────────────┐
        │ Dedup engine        │  one opportunity, many sources
        └─────────┬───────────┘
                  ▼
        ┌─────────────────────┐        ┌─────────────────────┐
        │ AGENT 3 Verifier    │        │ Verification results│
        │ 10 checks → status  │        │ (audit log)         │
        └─────────┬───────────┘        └─────────────────────┘
                  ▼
        ┌─────────────────────┐        ┌─────────────────────┐
        │ AGENT 4 Eligibility │ ◄─────►│ MASTER PROFILE      │
        │ + Matcher + Ranker  │        │ (single source of   │
        │ (deterministic)     │        │  truth)             │
        └─────────┬───────────┘        └─────────────────────┘
                  ▼
        Notifications: "HIGH MATCH" cards → user picks one
                  ▼
   AGENT 5 CV Tailor ──► AGENT 6 Cover Letter ──► FACTCHECK GATE
                                                     │  (drop unverified)
                                                     ▼
                     APPLICATION REVIEW (view CV / letter / answers)
                               [APPROVE & SUBMIT] [EDIT] [CANCEL]
                                                     │
                                                     ▼
                             AGENT 7 Application Assistant (Playwright)
                             auto-fill + save draft; STOPS before submit
                                                     ▼
                          APPLICATION TRACKER (statuses, events, follow-ups)
                                                     ▼
                             AGENT 8 Interview Prep (status = INTERVIEW)
                             question bank + mock interview + daily report
```

### 2.3 Why a modular monolith

- One deployable unit → simplest local run on Windows and simplest cloud deploy.
- Agents communicate via **database rows + typed messages**, not function calls — so each agent can later be split into its own worker/Celery task if volume ever grows, without rewriting logic.
- A shared `LLMProvider` and `FactCheck` service keeps every agent honest and cheap.

---

## 3. APIs vs Web Search vs Browser Automation

### 3.1 Decision rules

1. **If an official, documented API exists and we're eligible → use it.**
2. **Else if an RSS/JSON feed exists → use it** (cheapest, politest).
3. **Else if the content is a public page we may read → fetch it politely** (`requests`/Playwright read-only, honoring robots.txt and rate limits, with caching).
4. **Else (LinkedIn, Indeed, login-gated portals) → do NOT scrape.** Discover via search-engine snippets/API; application is manual or assist-mode with user present.

### 3.2 Source strategy matrix

| Category | Primary method | Free/cheap tool | Notes |
|---|---|---|---|
| General teaching jobs (Kenya + intl) | Web search API + LLM extraction | Google Programmable Search (CSE) 100/day free; Serper 2,500 one-time free; Tavily 1,000/mo free | Query each of the 25 search categories; extract structured JSON from snippets/landing pages |
| Kenya aggregators (BrighterMonday, Fuzu, MyJobMag) | Polite read-only fetch of search/list pages | `requests` + cache, or Playwright read-only | Respect robots.txt; no accounts |
| Adzuna (covers `adzuna.co.ke` + 16 countries) | **Official API** | Free tier ~1,000 calls/mo, self-serve app_id/key | Verify current country coverage at setup |
| Remote jobs | **Official APIs** | Remotive (no key), RemoteOK (no key), Arbeitnow (no key) | Remote + tech-heavy — great for AI-training/remote teaching |
| US federal jobs | **Official API** | USAJOBS API (free, public) | Only if user later targets US |
| ATS-direct feeds | **Official public JSON** | Greenhouse / Lever / Ashby boards APIs (no key) | Many international schools & EdTech firms use these — highest-signal source |
| International schools (TES, Teacher Horizons, Schrole, Search Associates) | Search discovery + assist-mode application | Web search + fetch of official school career pages | TES/Teacher Horizons: no public API; apply via assist mode where permitted |
| Government/UN/IO jobs | RSS/API | ReliefWeb API + RSS, UN Careers, AU careers, PSC Kenya | Free; strong for scholarships-adjacent and development roles |
| AI-training platforms (Outlier, DataAnnotation, Alignerr, Remotasks, Scale) | Web search discovery only | Search API; platform signup is manual/assisted | These platforms have no APIs and often require their own assessments |
| Scholarships (DAAD, Erasmus+, Chevening, Commonwealth, Mastercard Foundation, AIMS, etc.) | Fetch official programme pages + LLM extraction | `fetch` of official URLs; `site:` searches to confirm programme exists | **"Fully funded" only when official page says so** |
| LinkedIn / Indeed | Discovery via search snippets only; **no scraping, no automation** | Search API | ToS prohibit scraping & automation; applications manual |

**Search cadence** (configurable in `settings`): jobs 3×/day, scholarships 2×/day, high-priority sources 1×/day, all with result caching (content hash → skip re-extraction) and dedup.

---

## 4. Legal & Technical Limitations of Automated Applications

Honest assessment — these shape the Application Assistant design:

| Limitation | Implication for CareerPilot |
|---|---|
| **Job-board ToS** (LinkedIn, Indeed, most boards) prohibit scraping and bot submission | We never scrape them; discovery only via search APIs. Assisted applications only where ToS allow; user can paste/upload manually otherwise |
| **CAPTCHA / reCAPTCHA / Cloudflare** | Hard stop: the assistant pauses and asks the user to complete it. We never attempt to bypass |
| **Login-gated portals** | Assist mode only: auto-fill fields *after the user logs in*; never store portal passwords |
| **Kenya — Data Protection Act 2019** | PII (phone, ID, TSC number) encrypted at rest; minimal retention; user-owned data; audit trail |
| **Kenya — Computer Misuse & Cybercrimes Act 2017** | We do not circumvent access controls; we only automate what a human could do with consent on sites that permit it |
| **GDPR (EU orgs / EU-hosted forms)** | Data minimization, right to erasure (user can delete all records), consent = user's own action |
| **Sensitive attestations** — criminal record, disability, diversity, visa/immigration, identity verification, salary expectations, "is all information true", legal declarations | **Hard-blocked from auto-fill.** The assistant stops and shows the exact question; user types the answer or skips. Never guessed, never drafted by AI |
| **Scholarship essay authenticity** | Drafts + fact-check + human rewrite; never auto-submit |
| **Site redesigns breaking selectors** | Application "recipes" (per-site selector maps) + label/placeholder heuristics + human fallback |
| **Bans/account risk** | Default mode = assist (user clicks final buttons); "auto" mode only after per-site opt-in |

**Design consequence:** the Application Assistant has two modes:
- **ASSIST (default):** opens the page, fills non-sensitive fields, saves drafts, stops at the review gate and at any blocked field.
- **AUTO:** additionally clicks submit *only for sites the user explicitly whitelisted*, and even then only after the `APPLY / EDIT / CANCEL` approval card.

---

## 5. Database Schema

### 5.1 ERD (logical)

```
users 1─∞ master_profiles 1─∞ education / experience / skills / certifications
users 1─∞ documents 1─∞ document_extractions
organizations 1─∞ jobs 1─∞ job_sources (many sources per job → dedup)
jobs 1─∞ verification_results          scholarships 1─∞ verification_results
jobs/scholarships 1─∞ applications 1─∞ application_answers
                                   ├─∞ application_events (audit trail)
                                   ├─1 cv_versions ─1─1 fact-check report
                                   ├─1 cover_letters ─1─1 fact-check report
                                   └─1 interviews 1─∞ interview_questions
deadlines ─ referenced by jobs/scholarships/applications
notifications ─ (users, channels, pref table)
search_sources / search_runs / result_cache (discovery layer)
llm_usage_log (cost tracking)         settings (weights, cadence, prefs)
```

### 5.2 DDL (SQLite-compatible; PostgreSQL notes inline)

```sql
-- ══════════ CORE IDENTITY ══════════
CREATE TABLE users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,              -- bcrypt
    full_name     TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT
);

CREATE TABLE master_profiles (
    id                        INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id                   INTEGER NOT NULL REFERENCES users(id),
    full_name                 TEXT NOT NULL,
    nationality               TEXT,
    location                  TEXT,
    phone_encrypted           TEXT,           -- Fernet-encrypted PII
    email                     TEXT,
    profession                TEXT,
    summary                   TEXT,
    professional_registration TEXT,           -- e.g., TSC registered teacher
    is_active                 INTEGER DEFAULT 1,
    created_at                TEXT, updated_at TEXT
);

CREATE TABLE education (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id   INTEGER NOT NULL REFERENCES master_profiles(id),
    degree       TEXT, institution TEXT, field TEXT,
    classification TEXT,                     -- e.g., First Class Honours
    start_date   TEXT, end_date TEXT, is_current INTEGER DEFAULT 0,
    notes        TEXT
);

CREATE TABLE experience (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id   INTEGER NOT NULL REFERENCES master_profiles(id),
    organization TEXT, role TEXT, location TEXT,
    start_date   TEXT, end_date TEXT, is_current INTEGER DEFAULT 0,
    subjects     TEXT,                        -- JSON array
    grades       TEXT,                        -- JSON array
    description  TEXT
);

CREATE TABLE skills (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL REFERENCES master_profiles(id),
    name       TEXT NOT NULL,
    category   TEXT,                          -- teaching / tech / pedagogy ...
    level      TEXT,                          -- basic / proficient / advanced
    approved   INTEGER DEFAULT 1,             -- 0 = extracted, pending user approval
    source     TEXT                           -- 'USER APPROVED' | 'EXTRACTED' | 'LLM'
);

CREATE TABLE certifications (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id   INTEGER NOT NULL REFERENCES master_profiles(id),
    name         TEXT, issuer TEXT, date_earned TEXT, reference_number TEXT
);

CREATE TABLE documents (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL REFERENCES users(id),
    file_name     TEXT, file_path TEXT,
    doc_type      TEXT,                       -- CV / transcript / degree / TSC / ...
    extraction_status TEXT,                   -- PENDING / DONE / FAILED
    uploaded_at   TEXT
);

CREATE TABLE document_extractions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id  INTEGER NOT NULL REFERENCES documents(id),
    field_name   TEXT, field_value TEXT,
    status       TEXT CHECK(status IN ('VERIFIED','UNVERIFIED','USER CONFIRMED')),
    created_at   TEXT
);
-- NOTE: extracted info is UNVERIFIED until the user confirms; it is NEVER
-- auto-added to the master profile (spec §17).

-- ══════════ OPPORTUNITIES ══════════
CREATE TABLE organizations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    website TEXT, type TEXT, country TEXT,
    verified INTEGER DEFAULT 0, notes TEXT
);

CREATE TABLE jobs (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    title                   TEXT NOT NULL,
    organization_id         INTEGER REFERENCES organizations(id),
    organization_name       TEXT,
    location                TEXT, country TEXT,
    employment_type         TEXT,
    salary_min REAL, salary_max REAL, salary_currency TEXT,
    description             TEXT,
    requirements            TEXT,              -- JSON array (must-have)
    preferred_requirements  TEXT,              -- JSON array (nice-to-have)
    deadline                TEXT,
    application_url         TEXT, source_url TEXT,
    remote                  INTEGER DEFAULT 0,
    is_international        INTEGER DEFAULT 0,
    curriculum              TEXT,              -- CBC / IGCSE / A-Level / IB / ...
    discovery_date          TEXT,
    verification_status     TEXT CHECK(verification_status IN
        ('VERIFIED','LIKELY VERIFIED','UNVERIFIED','SUSPICIOUS','EXPIRED')),
    verification_notes      TEXT,
    duplicate_group         TEXT,              -- cluster id
    is_canonical            INTEGER DEFAULT 1, -- 1 = the record we keep
    eligibility             TEXT,              -- ELIGIBLE / POSSIBLY / NOT
    match_score             REAL, priority_score REAL,
    is_ai_training          INTEGER DEFAULT 0,
    status                  TEXT DEFAULT 'DISCOVERED',
    created_at TEXT, updated_at TEXT
);

CREATE TABLE job_sources (                      -- dedup: one job, many sources
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL REFERENCES jobs(id),
    source_type TEXT, source_name TEXT, source_url TEXT, fetched_at TEXT
);

CREATE TABLE scholarships (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    name                    TEXT NOT NULL,
    university              TEXT, country TEXT,
    programme               TEXT, degree_level TEXT,
    funding_level           TEXT,               -- FULLY FUNDED / PARTIAL / TUITION / ...
    tuition_coverage TEXT, accommodation TEXT, living_allowance TEXT,
    travel_allowance TEXT, insurance TEXT, application_fee TEXT,
    eligibility             TEXT,
    required_classification TEXT, required_field TEXT,
    work_experience_required TEXT, english_requirement TEXT, age_requirement TEXT,
    deadline                TEXT,
    application_url TEXT, official_url TEXT,
    open_to_kenyans INTEGER DEFAULT 0, open_to_africans INTEGER DEFAULT 0,
    verification_status TEXT, verification_notes TEXT,
    match_score REAL, eligibility TEXT,
    discovery_date TEXT, status TEXT,
    duplicate_group TEXT, is_canonical INTEGER DEFAULT 1,
    created_at TEXT, updated_at TEXT
);

-- ══════════ VERIFICATION ══════════
CREATE TABLE verification_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT,                           -- job / scholarship / org / url
    entity_id INTEGER,
    check_name TEXT, passed INTEGER, details TEXT,
    result TEXT,                                -- final classification
    checked_at TEXT
);

-- ══════════ APPLICATIONS & TRACKING ══════════
CREATE TABLE applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    job_id INTEGER REFERENCES jobs(id),
    scholarship_id INTEGER REFERENCES scholarships(id),
    status TEXT CHECK(status IN
        ('DISCOVERED','VERIFIED','SHORTLISTED BY AGENT','READY FOR REVIEW',
         'APPROVED','APPLIED','INTERVIEW','OFFER','REJECTED','WITHDRAWN','EXPIRED')),
    match_score REAL, priority_score REAL,
    cv_version_id INTEGER, cover_letter_id INTEGER,
    deadline TEXT, salary TEXT,
    contact_person TEXT, contact_email TEXT,
    date_discovered TEXT, date_applied TEXT,
    interview_date TEXT, follow_up_date TEXT,
    outcome TEXT, notes TEXT,
    created_at TEXT, updated_at TEXT
);

CREATE TABLE application_events (               -- audit trail
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER NOT NULL REFERENCES applications(id),
    event_type TEXT, description TEXT, created_at TEXT
);

CREATE TABLE application_answers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER NOT NULL REFERENCES applications(id),
    field_name TEXT, question TEXT, answer TEXT,
    requires_approval INTEGER DEFAULT 0,        -- 1 = sensitive field, hard block
    approved INTEGER DEFAULT 0,
    created_at TEXT, updated_at TEXT
);

CREATE TABLE cv_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER, application_id INTEGER,
    target_role TEXT, version_label TEXT,
    file_path TEXT, json_snapshot TEXT,         -- the exact data used
    fact_check_report TEXT,                     -- every claim + VERIFIED/NO
    created_at TEXT
);

CREATE TABLE cover_letters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER, application_id INTEGER,
    content TEXT, file_path TEXT,
    fact_check_report TEXT, created_at TEXT
);

-- ══════════ INTERVIEWS ══════════
CREATE TABLE interviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER NOT NULL REFERENCES applications(id),
    interview_date TEXT, format TEXT, panel TEXT, notes TEXT
);

CREATE TABLE interview_questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    interview_id INTEGER REFERENCES interviews(id),
    category TEXT,                              -- pedagogy / CBE / subject / ...
    question TEXT, model_answer TEXT, difficulty TEXT
);

-- ══════════ DEADLINES, NOTIFICATIONS ══════════
CREATE TABLE deadlines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT, entity_id INTEGER, due_date TEXT,
    reminder_days INTEGER DEFAULT 3, notified INTEGER DEFAULT 0
);

CREATE TABLE notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    type TEXT, title TEXT, body TEXT, channel TEXT,
    is_read INTEGER DEFAULT 0, sent_at TEXT, created_at TEXT
);

CREATE TABLE notification_preferences (
    user_id INTEGER PRIMARY KEY,
    in_app INTEGER DEFAULT 1, email INTEGER DEFAULT 0,
    telegram INTEGER DEFAULT 0, whatsapp INTEGER DEFAULT 0,   -- whatsapp = paid, optional
    high_match_job INTEGER DEFAULT 1,
    high_eligibility_scholarship INTEGER DEFAULT 1,
    deadline_approaching INTEGER DEFAULT 1,
    application_ready INTEGER DEFAULT 1,
    interview_scheduled INTEGER DEFAULT 1,
    followup_due INTEGER DEFAULT 1,
    expired INTEGER DEFAULT 1
);

-- ══════════ SEARCH LAYER ══════════
CREATE TABLE search_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT, kind TEXT,                       -- API / RSS / FETCH / SEARCH
    url TEXT, category TEXT, enabled INTEGER DEFAULT 1,
    cadence TEXT, last_run_at TEXT, notes TEXT
);

CREATE TABLE search_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER, query TEXT,
    started_at TEXT, finished_at TEXT,
    results_found INTEGER, new_opportunities INTEGER, error TEXT
);

CREATE TABLE result_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type TEXT, query TEXT, url TEXT,
    content_hash TEXT, fetched_at TEXT
);

-- ══════════ SETTINGS & TELEMETRY ══════════
CREATE TABLE settings (
    user_id INTEGER, key TEXT, value TEXT,
    PRIMARY KEY (user_id, key)
);
-- e.g., priority_weights (JSON), search_cadence, timezone=Africa/Nairobi,
-- llm_provider, notification prefs, deadline_reminder_days

CREATE TABLE llm_usage_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT, model TEXT, task TEXT,
    input_tokens INTEGER, output_tokens INTEGER,
    cost_estimate REAL, created_at TEXT
);
```

**PostgreSQL notes (Phase 11+):** swap `AUTOINCREMENT`→`IDENTITY`/`BIGSERIAL`, `TEXT` JSON→`JSONB` (indexable), add `CITEXT` for emails, optional UUID PKs. The SQLAlchemy models are written once; only the engine/URL changes.

---

## 6. Folder Structure

```
careerpilot/
├── README.md
├── .gitignore                      # .env, data/, node_modules, .venv ...
├── .env.example                    # ALL keys documented, none committed
├── docker-compose.yml              # Phase 11 (optional cloud path)
├── backend/
│   ├── requirements.txt
│   ├── alembic/                    # DB migrations
│   ├── app/
│   │   ├── main.py                 # FastAPI entry (includes scheduler boot)
│   │   ├── core/
│   │   │   ├── config.py           # pydantic-settings ← env vars
│   │   │   ├── security.py         # bcrypt, JWT access/refresh
│   │   │   ├── crypto.py           # Fernet PII encryption
│   │   │   ├── db.py               # SQLAlchemy engine/session (sqlite/postgres)
│   │   │   └── llm.py              # LLMProvider abstraction + fallbacks
│   │   ├── models/                 # ORM (mirrors §5)
│   │   ├── schemas/                # Pydantic request/response + opportunity JSON
│   │   ├── api/
│   │   │   ├── deps.py
│   │   │   └── routers/            # auth, profile, jobs, scholarships,
│   │   │                           # applications, documents, cv, cover_letters,
│   │   │                           # interviews, notifications, settings, dashboard
│   │   ├── agents/
│   │   │   ├── base.py             # Agent ABC + run/audit logging
│   │   │   ├── job_scout.py        # AGENT 1
│   │   │   ├── scholarship_scout.py# AGENT 2
│   │   │   ├── verifier.py         # AGENT 3
│   │   │   ├── eligibility.py      # AGENT 4 (scoring)
│   │   │   ├── matcher.py          # AGENT 4 (ranking/priority)
│   │   │   ├── cv_tailor.py        # AGENT 5
│   │   │   ├── cover_letter.py     # AGENT 6
│   │   │   ├── fact_check.py       # ANTI-FABRICATION GATE (shared)
│   │   │   ├── application_assistant.py  # AGENT 7 (Playwright)
│   │   │   ├── interview_prep.py   # AGENT 8
│   │   │   └── report.py           # daily career report
│   │   ├── services/
│   │   │   ├── sources/            # adapters: adzuna, remotiva/remoteok/arbeitnow,
│   │   │   │                       #   google_cse, serper, tavily, rss, ats_feeds,
│   │   │   │                       #   playwright_fetch, reliefweb ...
│   │   │   ├── dedup.py            # duplicate clustering
│   │   │   ├── scoring.py          # eligibility rubric + priority weights
│   │   │   ├── notifications.py    # in-app, email (SMTP), telegram
│   │   │   ├── documents.py        # PDF/docx extraction (pymupdf, pdfplumber, OCR)
│   │   │   ├── docxgen.py          # ATS-friendly .docx generation (python-docx)
│   │   │   └── scheduler.py        # APScheduler jobs
│   │   ├── prompts/                # YAML templates (one per task, §8)
│   │   │   ├── job_extraction.yaml
│   │   │   ├── scholarship_extraction.yaml
│   │   │   ├── verification.yaml
│   │   │   ├── eligibility.yaml
│   │   │   ├── cv_tailoring.yaml
│   │   │   ├── cover_letter.yaml
│   │   │   ├── application_answers.yaml
│   │   │   ├── interview_prep.yaml
│   │   │   ├── daily_report.yaml
│   │   │   └── fact_check.yaml
│   │   └── workers/                # entrypoints for scheduled jobs
│   └── tests/
│       ├── test_scoring.py
│       ├── test_fact_check.py      # anti-fabrication cases
│       ├── test_dedup.py
│       ├── test_verifier.py
│       ├── test_sources_adzuna.py  # mocked
│       └── fixtures/               # sample JD JSON, profile JSON, PDFs
├── frontend/
│   ├── package.json
│   ├── next.config.js
│   ├── tailwind.config.ts
│   ├── app/                        # App Router pages
│   │   ├── login/  dashboard/  jobs/  scholarships/  applications/
│   │   ├── documents/  cv-builder/  cover-letters/  interviews/
│   │   ├── profile/  settings/
│   │   └── layout.tsx
│   ├── components/                 # cards, charts (recharts), forms,
│   │   │                           # application-review modal, mock-interview chat
│   ├── lib/                        # API client, auth store
│   └── public/
├── data/                           # GITIGNORED
│   ├── careerpilot.db              # SQLite (dev)
│   ├── uploads/                    # certificates, transcripts ...
│   └── generated/                  # tailored CVs, cover letters, exports
├── scripts/
│   ├── init_db.py
│   ├── seed_demo.py                # demo profile + sample opportunities
│   └── run_dev.ps1 / run_dev.bat   # Windows one-click launcher
└── docs/
    ├── 01-architecture-proposal.md # THIS FILE
    └── 02-phases.md                # phase log after approval
```

---

## 7. Agent Architecture

All agents extend `Agent` (runs are logged to `application_events`/`search_runs`; LLM calls logged to `llm_usage_log`). Every agent receives **structured JSON** (Pydantic schemas), not raw text.

| # | Agent | Input | Process | Output |
|---|---|---|---|---|
| 1 | **JobScout** | 25 search categories × configured sources | Fires source adapters (API/RSS/search), polite fetch; passes raw items to normalizer | Normalized `jobs` rows (JSON per §21), pending verification |
| 2 | **ScholarshipScout** | 12 search areas + prioritization flags | Same pipeline against scholarship sources; collects all 19 required scholarship fields | Normalized `scholarships` rows |
| 3 | **Verifier** | Opportunity + source URLs | 10 deterministic checks (§11) + optional LLM explanation | `verification_status` + `verification_results` log |
| 4 | **Eligibility Analyst + Matcher** | Opportunity + master profile | Deterministic 100-pt rubric (§10) → ELIGIBLE/POSSIBLY/NOT + strengths/gaps/risks/missing; priority score | Scores, ranked shortlist, notification cards |
| 5 | **CV Tailor** | JD JSON + profile + target role | JD analysis → keyword/section weighting → ATS .docx from profile data only → **FactCheck** | Tailored CV file + `cv_versions` row + fact-check report |
| 6 | **Cover Letter** | Org, role, JD, values, profile | LLM draft constrained to profile facts → **FactCheck** → human edit | Letter text/file + `cover_letters` row |
| 7 | **Application Assistant** | Application + CV + letter + site recipe | Playwright: login (user), auto-fill non-sensitive fields, save draft, **STOP** | Application review card → APPROVE/EDIT/CANCEL |
| 8 | **Interview Prep** | JD + profile + school info | LLM generates categorized question bank; mock interview chat | `interview_questions`, mock session, feedback |
| — | **FactCheck gate** (shared) | Any generated doc | Claim extraction → claim-vs-profile verification → drop unverified → blocklist scan | Fact-check report; gate blocks delivery on unverified claims |

**Coordinator:** the scheduler runs discovery → verification → scoring as a pipeline every cycle. Ranking and notifications follow. Document generation and applications are **user-triggered** (never automatic).

---

## 8. AI Prompting System

No giant prompts. Each task has a dedicated YAML template with: system prompt, input JSON schema, output JSON schema (validated with Pydantic + `response_format`/JSON mode), temperature (extraction = 0.0, generation = 0.4), and model tier (extraction: cheapest flash-class; generation: standard-class; analysis: standard-class).

| Prompt | Input (structured) | Output (structured) |
|---|---|---|
| `job_extraction` | raw listing text/HTML + source | `jobs` JSON per spec §21 |
| `scholarship_extraction` | page text + URL | all 19 scholarship fields |
| `verification` | opportunity JSON + check results | explanation only (checks are deterministic) |
| `eligibility` | requirement list + profile facts | strengths / gaps / risks / missing requirements (text) |
| `cv_tailoring` | JD JSON + profile JSON + target role | section plan + keyword weighting + content blocks drawn ONLY from profile |
| `cover_letter` | org/role/JD/values + profile facts | letter draft (400–550 words) |
| `application_answers` | question + profile facts + JD | answer draft (flagged sensitive → refuse) |
| `interview_prep` | JD + profile + school info | question bank JSON (categories, difficulty, model answers) |
| `fact_check` | claim list + profile facts | claim → VERIFIED / UNVERIFIED / UNSUPPORTED |
| `daily_report` | today's ranked items + profile | report markdown |

**Example (`prompts/job_extraction.yaml`, abbreviated):**

```yaml
name: job_extraction
model_tier: flash           # cheapest capable tier
temperature: 0.0
system: >
  You are a strict data extractor. Extract ONLY facts present in the listing.
  Never infer, never invent. If a field is absent, set it to null.
  Output must match the provided JSON schema exactly.
input_schema: job_listing_raw
output_schema: job_record        # Pydantic schema from app/schemas/opportunity.py
guardrails:
  - salary: only if explicitly stated
  - requirements: must-be vs preferred must be split; unknown → null
  - never mark FULLY_FUNDED unless the source text literally says so
```

---

## 9. Anti-Fabrication System (FactCheck Gate)

This is the most important subsystem. Design:

1. **Master profile = single source of truth.** All facts are typed entries (`education`, `experience`, `skills`, `certifications`, `registration`) with IDs. The profile can only change through explicit user action.
2. **Generation is context-constrained.** The LLM receives *only* profile facts selected as relevant (e.g., for a CS job: computer studies experience, HTML/CSS/JS/Python skills — not "integrated science"). The system prompt forbids adding anything outside the provided context.
3. **Claim extraction.** After drafting, a cheap flash-model call (or deterministic regex) extracts every factual claim: "B.Ed (Mathematics & Computer Studies)", "TSC-registered teacher", "taught Form 3 and Form 4", "proficient in Python".
4. **Verification.** Each claim is matched against profile entries (exact/alias match, date arithmetic for experience lengths). Result: `VERIFIED` / `UNVERIFIED` / `UNSUPPORTED`.
5. **Enforcement.** Unverified/unsupported claims are **removed** (regenerated or edited out). The document is not released until the report is clean.
6. **Static blocklist.** A rule engine flags fabrication patterns regardless of LLM output, e.g.:
   - Years-of-experience claims not derivable from profile dates
   - Any institution/employer not in the profile
   - Any skill/certification not in the profile
   - "International school experience", "IB/IGCSE teaching" — only if the profile explicitly contains them (it doesn't, so these can never appear)
   - Salary history, awards, references, grades not listed
7. **Versioning.** Every `cv_versions` / `cover_letters` row stores the exact JSON snapshot used + the fact-check report, so any document can be audited forever.
8. **Human review.** All documents are viewable/editable before use.

**Fabrication is therefore a pipeline rejection** — the model cannot insert it and the gate deletes it if it tries.

---

## 10. Scoring & Ranking

### 10.1 Eligibility score (0–100) — matches spec weights

| Component | Weight | Deterministic inputs |
|---|---|---|
| Education | 20 | Degree level required vs held; field match; classification |
| Subject match | 20 | JD subject keywords (Mathematics, Computer Studies, ICT…) vs profile subjects |
| Experience | 20 | Required experience type/years vs profile (date-arithmetic only) |
| Technical skills | 15 | JD-required skills vs profile skills (only JD-listed skills count) |
| Professional registration | 10 | TSC required? registered? |
| Location eligibility | 10 | Kenya on-site / remote / international (relocation = user opt-in setting) |
| Other requirements | 5 | e.g., curriculum (CBC/CBE vs IGCSE — mismatch is a **gap**, not hidden) |

→ Output: **MATCH SCORE**, `ELIGIBLE / POSSIBLY ELIGIBLE / NOT ELIGIBLE`, plus **STRENGTHS, GAPS, RISKS, MISSING REQUIREMENTS**. Missing requirements are never hidden (spec §6).

### 10.2 Relevance score
Semantic overlap of JD with profile (keyword/Jaccard default; optional embedding upgrade). Used inside priority, not alone.

### 10.3 Priority score (configurable weights)

```
PRIORITY = 0.30·Eligibility + 0.25·Relevance + 0.15·Career growth*
          + 0.10·Compensation/Funding + 0.10·Deadline urgency + 0.10·Org quality
* career growth = heuristic (title level, institution reputation score, AI-training premium)
```

Weights live in `settings` and are editable in the UI.

---

## 11. Verification Engine (Agent 3)

The 10 spec checks → deterministic signals:

| # | Check | Signal |
|---|---|---|
| 1 | Org exists | Org name → web search → official domain found; domain has valid TLS; MX records for contact email |
| 2 | Listed on official/reputable source | source domain in allowlist or = org domain |
| 3 | Application URL legitimate | https, host matches org domain, no typosquat (Levenshtein vs known domains), no URL-shortener redirect to unknown |
| 4 | Deadline valid | parse (with Africa/Nairobi TZ) vs now; expired → EXPIRED |
| 5 | Duplicate | dedup cluster exists? merge sources |
| 6 | Job actually exists | ≥2 independent sources, or successful fetch of official listing |
| 7 | Payment requirements | keyword scan (fee, processing, bank transfer, gift card, crypto, "guaranteed", "visa fee", "registration fee") → SUSPICIOUS |
| 8 | Scholarship exists | official page fetched successfully |
| 9 | Programme on university site | `site:university.edu` search or programme-page fetch |
| 10 | Process consistency | e.g., official says "apply via portal" but ad says "email gmail.com" → SUSPICIOUS |

**Classification:** all checks pass → `VERIFIED`; minor unknowns, no red flags → `LIKELY VERIFIED`; cannot confirm → `UNVERIFIED`; any red flag → `SUSPICIOUS` (**never recommended**); deadline passed → `EXPIRED`. Human overrides logged.

---

## 12. Deduplication & Caching

- **Normalized key:** `lower(title) · lower(org) · country` + optional salary bucket.
- **Fuzzy cluster:** Jaccard/TF-IDF similarity on description > 0.9 → same cluster. One canonical row; others become sources in `job_sources`.
- **Cache:** content hash per URL in `result_cache` — unchanged pages are not re-extracted, honoring spec §15.
- Cadence defaults: jobs 3×/day, scholarships 2×/day, high-priority 1×/day; all configurable; no aggressive polling.

---

## 13. Notifications & Daily Report

- **Events:** high-match job found, high-eligibility scholarship, deadline approaching (−7/−3/−1 days, configurable), application ready, interview scheduled, follow-up due, opportunity expired.
- **Channels (configurable):** in-app (default), **email** (Gmail SMTP app-password — free), **Telegram** (Bot API — free). **WhatsApp** = paid (Meta Cloud API/Twilio) → optional Phase 11+.
- **Daily report (06:30 Nairobi, configurable):** "GOOD MORNING JOHN — 5 HIGH MATCH TEACHING JOBS · 3 AI TRAINING JOBS · 2 SCHOLARSHIPS. Top recommendation: Computer Science & Mathematics Teacher, Match 94%. Why: ✓ B.Ed (Math & CS) ✓ First Class ✓ TSC ✓ CS experience ✓ Math experience. Gap: ⚠ International curriculum experience. Action: APPLY." Sent to selected channels, stored in-app.

---

## 14. Application Assistant (Agent 7) — Human-in-the-Loop

- **Playwright (Python).** Per-site "recipe" (JSON: URL pattern, selectors, field map, login notes) + generic heuristics (label/placeholder matching against profile fields).
- **Auto-filled (non-sensitive):** name, email, phone, location, work history, education, skills, CV/letter uploads, standard questions → draft answers.
- **Hard-stop fields (never auto-filled, never guessed):** TSC number, ID/passport numbers, criminal-record questions, legal declarations, visa/immigration declarations, salary expectations, diversity/disability questions, "is this information true" attestations, CAPTCHA, any unfamiliar field → show the exact question, require typed user input, or skip.
- **Review gate before submission:**

```
APPLICATION REVIEW
Company:   …      Position: …      URL: …
CV: [View]      Cover Letter: [View]      Application Answers: [View]
[APPROVE & SUBMIT]   [EDIT]   [CANCEL]
```

- Every action logged to `application_events`.

---

## 15. Development Phases (per spec §26)

Each phase = explain → show structure → working code → how to run → tests → limitations → **wait for approval**.

| Phase | Deliverables | Exit test |
|---|---|---|
| **0 (now)** | This proposal | ✅ your approval |
| **1** | Skeleton: FastAPI + config + auth + DB (SQLite) + migrations + master profile CRUD + opportunity schemas + seed script | `pytest` auth/profile; seed demo profile; API docs at `/docs` |
| **2** | JobScout: source adapters (Adzuna, Remotive/RemoteOK/Arbeitnow, CSE/Serper/Tavily, RSS), normalizer, dedup, caching | Mocked-adapter tests; live run finds ≥10 real Kenya/intl teaching jobs into DB |
| **3** | ScholarshipScout: same pipeline for scholarships, 19-field capture, official-page confirmation | Mocked + live test on 3 real scholarships |
| **4** | Verifier: 10 checks, classifications, human override | Tests: scam fixture → SUSPICIOUS; valid fixture → VERIFIED |
| **5** | Eligibility + Matcher + ranking + notifications (in-app/email/Telegram) + priority weights | Tests on rubric; scores reproduce expected values for crafted cases |
| **6** | CV Tailor: JD analysis, ATS .docx generation, **FactCheck gate**, versioning, CV builder UI | FactCheck test: injected fake claim is removed; ATS parse of generated docx |
| **7** | Cover Letter generator + FactCheck + editor | Cover letter for a sample school; no unverified claims |
| **8** | Dashboard (Next.js): all pages, job/scholarship cards, tracker, documents, settings | E2E: login → browse opportunities → create application |
| **9** | Application Assistant (Playwright) + review gate + sensitive-field rules | Dry-run against a disposable test form; gate blocks auto-submit; sensitive fields pause |
| **10** | Interview Prep + mock interview chat + daily report | Generate question bank for a sample JD; run a mock session |
| **11 (planned)** | Cloud deployment, Postgres, backups, WhatsApp (optional), embedding-based relevance | Deployed on target host; CI green |

---

## 16. Technology Stack & Free/Low-Cost Tools

| Layer | Choice | Cost |
|---|---|---|
| Backend | Python 3.11+ · FastAPI · SQLAlchemy 2 · Pydantic v2 · APScheduler | Free |
| DB | SQLite (dev) → PostgreSQL via Neon/Supabase free tier (prod) | Free |
| LLM | Provider abstraction: **Gemini Flash (AI Studio free tier, ~1,500 req/day)** default; fallback Groq (free tier); optional Ollama (local, free); paid upgrades: OpenAI GPT-4.1-mini, Claude Haiku | **$0** base |
| Search | Google CSE (100/day free) · Serper (2,500 one-time free credits) · Tavily (1,000/mo free) · Brave (now $5/mo credit — optional) | **$0** base |
| Job APIs | Adzuna (~1,000 calls/mo free) · Remotive · RemoteOK · Arbeitnow · USAJOBS · ATS feeds (Greenhouse/Lever/Ashby) · ReliefWeb | Free |
| Scraping/automation | Playwright (Python) | Free |
| Frontend | Next.js (App Router) · Tailwind CSS · shadcn/ui · recharts | Free |
| Docs processing | PyMuPDF · pdfplumber · python-docx · Tesseract OCR | Free |
| Email | Gmail SMTP app password; optional Resend free tier (3,000/mo) | Free |
| Messaging | Telegram Bot API | Free |
| Scheduling | APScheduler in-process (no Redis/Celery needed at this scale) | Free |
| Cloud (later) | Railway free tier / Render free tier, or Hetzner CX22 VPS (~€4/mo) · Caddy for HTTPS · Backblaze B2 free 10 GB for uploads | $0–5/mo |

---

## 17. Running on Windows PC (local, Phase 1–10)

1. Install **Python 3.11+** (python.org, tick *Add to PATH*) and **Node.js 20 LTS**.
2. `git clone <repo>` → `cd careerpilot`.
3. Backend:
   - `python -m venv backend/.venv` → `backend\.venv\Scripts\activate`
   - `pip install -r backend\requirements.txt`
   - `playwright install chromium` (for Agent 7)
   - `copy .env.example .env` and fill keys (optional initially — demo mode works without LLM keys using seeded data)
   - `python scripts\init_db.py` → creates `data\careerpilot.db`
   - `uvicorn app.main:app --reload --port 8000` (scheduler auto-starts with the app)
4. Frontend: `cd frontend`, `npm install`, `npm run dev` → http://localhost:3000
5. One-click: `scripts\run_dev.bat` starts both.
6. Tests: `pytest backend\tests`.

---

## 18. Cloud Deployment Path (Phase 11+)

1. Dockerize backend (include Playwright browser via `mcr.microsoft.com/playwright` base image) and frontend; `docker-compose.yml` with Postgres.
2. Managed Postgres on **Neon** or **Supabase** free tier; uploads to Backblaze B2 (free 10 GB).
3. Deploy: **Railway** (simplest, free-ish) or **Render** (free tier spins down) or **Hetzner CX22 VPS (~€4/mo)** with Caddy for automatic HTTPS — recommended for a 24/7 scheduler + Playwright worker.
4. Secrets via platform env vars (never in the repo). GitHub Actions CI: lint + pytest on push.
5. `.env` same variable names on the host — zero code change.

---

## 19. Cost Estimate (monthly)

| Item | Free path | Paid escalation |
|---|---|---|
| LLM | Gemini Flash free tier: **$0** | GPT-4.1-mini/Claude Haiku at personal volume ≈ **$2–6** |
| Web search | CSE + Serper + Tavily free credits: **$0** | Brave $5/mo credit or Serper paid ≈ **$5** |
| Job APIs / RSS | **$0** | — |
| Email / Telegram / in-app | **$0** | — |
| Hosting | Local (free); cloud free tiers | Railway/Hetzner ≈ **$4–7** |
| Storage | Local; B2 free 10 GB | — |
| **Total** | **≈ $0/mo** | **≈ $5–15/mo worst case** |

A `llm_usage_log` table tracks real token spend so costs never surprise you.

---

## 20. Security & Data Protection

- Secrets only in `.env` (`.gitignore`); `.env.example` documents every variable.
- bcrypt password hashing; JWT access + refresh tokens; HTTPS in production.
- PII (phone, ID, TSC number) **Fernet-encrypted at rest**, decrypted only in memory when needed.
- Rate limiting on the API; audit events for every application action.
- Document uploads: type/size checks; PDF text extraction; extracted facts marked `UNVERIFIED` until user confirms (spec §17).
- Right to delete: a user can wipe all records/uploaded files.

---

## 21. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| LLM hallucination | FactCheck gate, temperature 0 for extraction, JSON-schema output, versioned snapshots |
| Free-tier quotas hit | Provider fallback chain (Gemini → Groq → Ollama → paid); usage log alert |
| Source ToS change / site redesign | Adapter isolation; recipes + heuristics; manual fallback |
| Dead links / stale deadlines | Re-verify at application time; EXPIRED auto-status |
| PII exposure | Encryption at rest, minimal retention, HTTPS, user delete-right |
| Deadline/date parsing errors | Explicit `Africa/Nairobi` TZ handling; human confirmation before APPLY |
| Playwright blocked | Assist mode default; CAPTCHA pause; manual submission always possible |
| Over-eager automation | Review gate + hard-blocked sensitive fields + per-site whitelist for auto mode |

---

## 22. Decisions Needed From You

Before Phase 1, please confirm (the questions are also in the chat):

1. **Approve this architecture** as-is, or request changes?
2. **Default LLM provider**: free-first (Gemini Flash + Groq fallback) — recommended? Or OpenAI/Anthropic (better quality, ~$2–6/mo) from day one?
3. **Notification channels**: Dashboard + Email + Telegram (recommended, free)? WhatsApp later (paid)?
4. **Cloud**: build local-only through Phase 10 and deploy in Phase 11 (recommended)? Or set up free-tier cloud hosting earlier?

Once approved, Phase 1 begins: project skeleton, database, master profile, and opportunity schema — with working code and tests, per spec §26.
