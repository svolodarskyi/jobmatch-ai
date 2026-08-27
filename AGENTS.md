# AGENTS.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

JobMatch AI — a single-user personal job-match engine for Canada. Pulls listings from Adzuna and Jooble, scores them against a profile, re-ranks the top matches via OpenAI, and presents results in a React dashboard with application-status tracking. Read `_docs/plan.md` and `_docs/architecture.md` before touching unfamiliar code.

## Commands

All commands assume you are in the relevant subdirectory unless noted.

### Backend (`backend/`)

```bash
# Install dependencies (editable mode)
pip install -e ".[dev]"

# Run dev server (reload on file change)
uvicorn app.main:app --reload --port 8000

# Run all tests
pytest

# Run a single test file
pytest tests/test_scoring.py

# Run a single test by name
pytest tests/test_scoring.py::test_skills_overlap

# Lint + type-check
ruff check . && mypy app/
```

### Frontend (`frontend/`)

```bash
npm install
npm run dev       # Vite dev server on port 5173
npm test          # Vitest (watch mode)
npm run test:run  # Vitest (CI / single pass)
npm run build     # Production build
npm run lint      # ESLint
```

### Docker (repo root)

```bash
docker compose up          # Bring up backend + frontend
docker compose up backend  # Backend only
docker compose build       # Rebuild images after dependency changes
```

## Architecture

Two containers, two external services. Read `_docs/architecture.md` for the full diagram.

- **`backend/`** — FastAPI. Owns all external API calls (Adzuna, Jooble, OpenAI) to avoid CORS and keep keys server-side. Runs the two-pass scoring pipeline and an APScheduler daily fetch. Exposes REST API on port 8000.
- **`frontend/`** — React + Vite. Talks only to the backend REST API. Port 5173 in dev.
- **Supabase** — hosted Postgres, not a container. Connected via `SUPABASE_URL` + `SUPABASE_SERVICE_KEY`.

## Backend layout

```
backend/
  app/
    main.py            # FastAPI app factory, mounts routers, starts scheduler
    settings.py        # pydantic-settings; fails fast on missing env vars
    db.py              # Supabase/Postgres session dependency
    pipeline.py        # Orchestrates fetch → normalize → persist → score → re-rank
    scheduler.py       # APScheduler daily job wired to pipeline.run()
    sources/
      adzuna.py        # Adzuna Canada API client
      jooble.py        # Jooble API client (country=CA)
      normalize.py     # Maps raw source payloads → canonical Job dataclass
    scoring/
      pass1.py         # Weighted 0-100 score — pure function, no I/O
      pass2.py         # OpenAI re-ranking for top 15-20 jobs
    routers/
      jobs.py          # GET /jobs, POST /fetch
      profile.py       # GET /profile, PUT /profile
      status.py        # PATCH /jobs/{id}/status, PATCH /jobs/{id}/notes
  tests/
```

## Key invariants

- **Dedup**: jobs are upserted on `(source, external_id)`. Re-fetching a listing must never create a duplicate row.
- **Pass 2 is capped**: only top 15–20 Pass 1 results go to OpenAI. Don't remove this cap; it controls cost.
- **Canada only**: every source query must include a Canada-specific filter (`country=ca` for Adzuna, `country=CA` for Jooble). Don't widen silently.
- **No keys in frontend**: all third-party API calls live in the backend. The frontend talks only to `localhost:8000`.

## Scoring weights

Pass 1 composite (0–100):

| Signal                | Weight |
| --------------------- | ------ |
| Skills overlap        | 40%    |
| Seniority match       | 20%    |
| Location / remote fit | 20%    |
| Salary range overlap  | 20%    |

`pass1.py` must remain a pure function (Job + Profile → score dict). Tests call it directly without a running app.

## Environment variables

All loaded from `.env` (gitignored). See `.env.example`.

| Variable               | Consumer            |
| ---------------------- | ------------------- |
| `ADZUNA_APP_ID`        | `sources/adzuna.py` |
| `ADZUNA_APP_KEY`       | `sources/adzuna.py` |
| `JOOBLE_API_KEY`       | `sources/jooble.py` |
| `OPENAI_API_KEY`       | `scoring/pass2.py`  |
| `SUPABASE_URL`         | `db.py`             |
| `SUPABASE_SERVICE_KEY` | `db.py`             |

## Testing conventions

- Source clients (Adzuna, Jooble) are always tested against recorded/mocked HTTP — no live network calls in tests.
- OpenAI calls in `pass2.py` are mocked in tests.
- `pass1.py` tests are pure unit tests with no mocking needed.
- DB tests use a mocked repository or a test Supabase project, never the production one.

## Documents

- `_docs/process.md` — how work is organized (issues, commits, closing tasks)
- Before writing tests, read `_docs/testing-guidelines.md`
- For anything touching the UI, read `_docs/design-system.md`
- For anything touching the REST API, read `_docs/api.md`
