# JobMatch AI — Architecture

## Overview

Single-user personal tool. Pulls Canadian job listings from Adzuna and Jooble,
scores them against a profile, re-ranks the top matches with an LLM, and presents
them in a dashboard with application status tracking.

## Services

```
┌─────────────────────────────────────────────────────────┐
│  docker-compose (local only, no deploy)                 │
│                                                         │
│  ┌──────────────────────┐   ┌───────────────────────┐  │
│  │  backend (FastAPI)   │   │  frontend (React)     │  │
│  │  port 8000           │◄──┤  port 5173 (Vite)    │  │
│  │                      │   │                       │  │
│  │  • REST API          │   │  • Dashboard          │  │
│  │  • Scoring engine    │   │  • Profile form       │  │
│  │  • APScheduler       │   │  • Job cards + filters│  │
│  │  • Adzuna client     │   │  • Status tracking    │  │
│  │  • Jooble client     │   └───────────────────────┘  │
│  │  • OpenAI client     │                               │
│  └──────────┬───────────┘                               │
└─────────────┼─────────────────────────────────────────-─┘
              │
              ▼  external services (not containerised)
┌─────────────────────────────────────────────────────────┐
│  Supabase (hosted Postgres)                             │
│  Adzuna API   |   Jooble API   |   OpenAI API           │
└─────────────────────────────────────────────────────────┘
```

## Backend (FastAPI)

**Responsibilities**
- Exposes REST API consumed by the frontend.
- Owns all external API calls (Adzuna, Jooble, OpenAI) to avoid CORS.
- Runs the two-pass scoring pipeline.
- Schedules the daily fetch via APScheduler.

**Key modules**

| Module | Role |
|---|---|
| `settings` | Loads env vars via pydantic-settings, fails fast if required ones are missing |
| `db` | Session/connection helper for Supabase Postgres |
| `sources/adzuna` | Adzuna Canada API client, returns raw listings |
| `sources/jooble` | Jooble API client (`country=CA`), returns raw listings |
| `sources/normalize` | Maps each source's raw payload to the canonical `Job` shape |
| `scoring/pass1` | Weighted 0–100 composite score (pure function, no I/O) |
| `scoring/pass2` | OpenAI re-ranking for top 15–20 jobs; returns score + rationale |
| `pipeline` | Orchestrates fetch → normalize → persist → score → re-rank |
| `routers/jobs` | `GET /jobs` (filtered, ordered by score), `POST /fetch` |
| `routers/profile` | `GET/PUT /profile` |
| `routers/status` | `PATCH /jobs/{id}/status`, `PATCH /jobs/{id}/notes` |
| `scheduler` | APScheduler daily job wired to `pipeline.run()` |

## Frontend (React + Vite)

Single-page app, no auth needed (single user).

**Views**

| View | Purpose |
|---|---|
| Dashboard | Ranked job cards with score, rationale, source, date, status |
| Filters bar | Score threshold, source, date, status — drives `GET /jobs` query params |
| Job card | Title, company, location, salary, LLM rationale, status selector, notes |
| Profile | Form for skills, seniority, locations, salary range, target titles |

## Database (Supabase / Postgres)

Three tables:

```
profile
  id            uuid pk
  target_titles text[]
  skills        text[]
  seniority     text
  locations     text[]
  salary_min    int
  salary_max    int
  preferences   jsonb

job
  id             uuid pk
  source         text          -- 'adzuna' | 'jooble'
  external_id    text
  title          text
  company        text
  location       text
  salary_min     int
  salary_max     int
  description    text
  url            text
  date_fetched   timestamptz
  raw_score      numeric       -- Pass 1 composite (0–100)
  llm_score      numeric       -- Pass 2 (nullable until re-ranked)
  llm_rationale  text
  UNIQUE (source, external_id)

application_status
  id           uuid pk
  job_id       uuid → job.id
  status       text    -- New | Saved | Applied | Interviewing | Rejected | Offer
  notes        text
  history      jsonb   -- [{status, changed_at}]
  updated_at   timestamptz
```

## Scoring Pipeline

```
Adzuna API  ──┐
              ├──► normalize ──► upsert (dedup on source+external_id)
Jooble API  ──┘

                    ▼ all stored jobs for this profile
               Pass 1: weighted score (0–100)
                    skills overlap   40 %
                    seniority match  20 %
                    location fit     20 %
                    salary overlap   20 %

                    ▼ top 15–20 by Pass 1 score
               Pass 2: OpenAI re-ranking
                    reads description vs. profile
                    returns llm_score + human rationale

                    ▼ persisted back to job table
```

**Fetch triggers**
- **Scheduled** — APScheduler runs `pipeline.run()` once per day while the container is up.
- **Manual** — `POST /fetch` endpoint; the dashboard "Fetch new jobs now" button hits this and refreshes the list.

## Environment Variables

| Variable | Used by |
|---|---|
| `ADZUNA_APP_ID` | Adzuna client |
| `ADZUNA_APP_KEY` | Adzuna client |
| `JOOBLE_API_KEY` | Jooble client |
| `OPENAI_API_KEY` | Pass 2 re-ranking |
| `SUPABASE_URL` | DB connection |
| `SUPABASE_SERVICE_KEY` | DB connection |

All loaded from `.env` (gitignored). See `.env.example` for the full list.

## Key Design Decisions

- **Backend owns all external calls** — no API keys in the browser; avoids CORS.
- **Dedup on `(source, external_id)`** — re-fetching the same listing never creates duplicates.
- **Pass 2 only on top 15–20** — keeps OpenAI costs low; most relevance signal comes from Pass 1.
- **Supabase external** — no DB container; two-service compose is simpler to run locally.
- **Canada only** — all source queries are locked to `country=CA`; scope never broadens silently.
