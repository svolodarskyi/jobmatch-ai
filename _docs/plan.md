# Project Scope: JobMatch AI — Personal Job Match Engine (Canada)

## 1. Problem Statement
A personal tool that continuously pulls job listings from multiple job-search APIs, scores them against a user-defined profile (skills, seniority, location, salary), and presents ranked matches in a dashboard — while tracking application status over time.

## 2. Naming Options
- **JobMatch AI**
- **Talent Radar**
- **CareerScout**
- **FitFinder**
- **JobCompass**
- **Sherlock Jobs** (keeps a "detective" wink, but about finding the *right* fit, not fraud)

*(Pick one, or we finalize later — doesn't block the build.)*

## 3. Users
- **Just you.** Single-user personal tool. No auth/multi-tenancy needed for MVP.

## 4. Core Features (MVP)

### 4.1 Profile Input
- Structured form, manually filled:
  - **Target job title(s)** (e.g., "Product Manager", "Data Analyst") — used to seed/narrow the API search queries
    - *Confirmed for this build:* **"Data Engineer", "Senior Data Engineer"** — both searched simultaneously (cast a wide net)
  - Skills (tags, e.g., "Python", "Product Management", "SQL")
    - *Confirmed for this build:* **Azure, Databricks, Microsoft Fabric, Azure Data Factory (ADF), Spark, Python, Airflow, CI/CD, AI tools**
  - Seniority level (Junior / Mid / Senior / Lead / Exec)
  - Location(s) — Canadian city/province (e.g., Calgary AB, Toronto ON) + remote preference
  - Desired salary range (CAD)
  - (Optional) Industry/company-type preferences

### 4.2 Job Aggregation
- **Scope: Canada only.** All source queries and location filters are locked to Canadian listings.
- **Search seeding: narrow.** Queries are built from the user's target job title(s), not a broad skills-based search — keeps API calls focused and result volume manageable.
- Pull listings from multiple job APIs on a schedule (e.g., daily).
- **Recommended sources** (confirmed Canada coverage):
  | Source | Notes |
  |---|---|
  | **Adzuna** | Free tier, has a dedicated Canada endpoint (`/v1/api/jobs/ca/...`), solid coverage |
  | **Jooble** | Free API, supports Canada via country param, good to cross-reference Adzuna |
  | **JSearch (via RapidAPI)** | Aggregates Indeed/LinkedIn/Glassdoor, location-filterable to Canada — richer but paid past free quota; good phase 2 add |
  | ~~Arbeitnow~~ | Dropped — mostly EU-focused, weak Canada coverage |
  | Remotive/RemoteOK | Only include if you want remote-anywhere roles too; otherwise skip since they're not Canada-specific |
- Start with **Adzuna + Jooble**, both queried with country=CA, no CORS issues since calls go through your backend.

### 4.3 Matching & Scoring (Hybrid Approach)
1. **Pass 1 — Weighted scoring** (fast, runs on every fetched job), composite score 0–100:
   - Skills overlap: **40%**
   - Seniority match: **20%**
   - Location/remote fit: **20%**
   - Salary range overlap: **20%**
2. **Pass 2 — OpenAI re-ranking** (only top 15–20 by score):
   - OpenAI reads job description vs. profile, gives a compatibility note (e.g., "Good skills match, but they want 5+ yrs leadership — you have 2").
   - Produces a short human-readable rationale per top match.

### 4.4 Dashboard
- Web app, accessible from anywhere.
- Ranked list/grid of matches with score + LLM rationale.
- Filters: score threshold, source, date fetched, status.
- Status tracking per job: **New → Saved → Applied → Interviewing → Rejected/Offer**.
- Notes field per job (freeform).
- History view: everything ever seen, regardless of current relevance, so nothing repeats/gets lost.

## 5. Data Model (high-level)
- **Profile**: skills, seniority, locations, salary range, preferences
- **Job**: source, external_id, title, company, location, salary, description, url, date_fetched, raw_score, llm_score, llm_rationale
- **ApplicationStatus**: job_id, status, notes, status_history (timestamps)

## 6. Architecture (Finalized)
- **Backend**: Python (FastAPI) — handles Adzuna/Jooble API calls (avoids CORS), scoring logic, OpenAI re-ranking calls, scheduled fetch jobs, exposes REST API to frontend.
- **Frontend**: React — dashboard UI (job list/cards, filters, status tracking, notes).
- **Database**: **Supabase (hosted Postgres)** — stores profile, jobs, application statuses/history. No local DB container needed since Supabase is already hosted.
- **LLM for Pass 2 re-ranking**: **OpenAI API** — reads top-scored job descriptions vs. profile, returns compatibility rationale.
- **Containerization**: Docker only, **no deployment** — runs locally via `docker-compose` with two services:
  - `backend` (FastAPI + scheduler)
  - `frontend` (React, served via dev server or a lightweight static server)
  - *(Supabase is external/hosted, so it's not a container — just connected via connection string/API keys from `.env`)*
- **Job fetching trigger — hybrid**:
  - **Auto**: a cron/scheduler (e.g., APScheduler inside the FastAPI backend) runs a daily fetch while the container is up.
  - **Manual**: a "Fetch new jobs now" button in the dashboard that hits a `/fetch` endpoint on demand — covers the case where the container isn't running 24/7 and you just want fresh results on open.

## 7. Phase 2 (Not MVP, but worth flagging)
- Resume upload → auto-extract skills instead of manual entry.
- Email/notification digest of new top matches.
- Auto-apply drafts (cover letter generation) for top matches.
- More sources (LinkedIn scraping is fragile/ToS-risky — skip unless specifically wanted).

## 8. Open Decisions — All Resolved ✅
- [x] Name: **JobMatch AI**
- [x] Region: Canada-only
- [x] Stack: FastAPI + React, Supabase (Postgres), OpenAI for re-ranking, Docker (no deploy)
- [x] Fetch trigger: auto (scheduler) + manual button
- [x] Scoring weights: skills 40% / seniority 20% / location 20% / salary 20%
- [x] Search seeding: narrow, driven by user-specified target job title(s)

## 9. Remaining Setup Tasks (not scope decisions, just accounts needed before coding)
- [ ] Adzuna API key (free signup)
- [ ] Jooble API key (free signup)
- [ ] OpenAI API key
- [ ] Supabase project created + connection string
