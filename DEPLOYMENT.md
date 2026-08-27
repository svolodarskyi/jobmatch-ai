# Deployment

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running
- Git (to clone the repository)
- Free accounts at:
  - [developer.adzuna.com](https://developer.adzuna.com/) — App ID + App Key
  - [jooble.org/api/about](https://jooble.org/api/about) — API Key
  - [platform.openai.com/api-keys](https://platform.openai.com/api-keys) — API Key (uses gpt-4o-mini; roughly $0.001 per fetch)
  - [supabase.com/dashboard](https://supabase.com/dashboard) — project URL + service_role key

## One-time setup

1. Copy `.env.example` to `.env` and fill in your six API keys:

   ```bash
   cp .env.example .env
   # Edit .env with your actual values
   ```

2. Apply the database migration in the Supabase SQL Editor:
   - Open your Supabase project → **SQL Editor**
   - Paste the entire contents of `backend/migrations/001_initial_schema.sql`
   - Click **Run**

   The migration is idempotent — running it again on an already-provisioned project is safe.

## Start the app

```bash
make build   # Build both Docker images (run once, and after dependency changes)
make up      # Start backend + frontend
```

- Backend API: [http://localhost:8000](http://localhost:8000)
- Frontend dashboard: [http://localhost:5173](http://localhost:5173)

The frontend waits for the backend health check to pass before starting (up to 30 seconds).

## First use

1. Open [http://localhost:5173](http://localhost:5173) in your browser.
2. Fill in the **Profile** form: target job titles, skills, seniority level, preferred locations, and salary range.
3. Click **Fetch new jobs** to trigger the first pipeline run. It pulls listings from the last 15 days (`FETCH_INITIAL_DAYS=15`).
4. Jobs appear in the dashboard ranked by match score. Use the status column to track applications.

## Day-to-day

The scheduler runs the fetch pipeline automatically once per day (`FETCH_INTERVAL_HOURS=24`). Each scheduled run pulls only the last day of new listings (`FETCH_INCREMENTAL_DAYS=1`).

Use the **Fetch new jobs** button in the dashboard for on-demand runs at any time.

## Stopping

```bash
make down    # Stop and remove containers (data in Supabase is preserved)
```

## Makefile reference

| Target           | What it does                                  |
| ---------------- | --------------------------------------------- |
| `make up`        | Start all services (`docker compose up`)      |
| `make down`      | Stop and remove containers                    |
| `make build`     | Build Docker images                           |
| `make logs`      | Tail logs from all services                   |
| `make test-backend`  | Run backend test suite (pytest)           |
| `make test-frontend` | Run frontend test suite (Vitest, CI mode) |
