# JobMatch AI — Task Backlog

Small, independent tasks derived from `_docs/plan.md`. Each is sized for a single
session and written so it can be handed off without reading the others. Where a task
assumes an interface from another (e.g. the `Job` model), the assumption is stated so
the task can proceed against a stub or agreed shape if the dependency isn't done yet.

Stack reference: FastAPI backend, React frontend, Supabase (hosted Postgres),
OpenAI for re-ranking, Docker Compose (local only, no deploy), sources Adzuna + Jooble.

---

## 1. Bootstrap backend project with a passing test
Goal: Create an empty FastAPI backend skeleton that runs one passing test.
Description: Set up a `backend/` Python project with dependency management (pyproject or requirements), install FastAPI and pytest, and add a minimal app with a `GET /health` endpoint returning `{"status": "ok"}`. Add a single test that calls the endpoint via FastAPI's TestClient and asserts a 200. Running the test suite should pass with zero other setup.

## 2. Bootstrap frontend project with a passing test
Goal: Create an empty React frontend skeleton that runs one passing test.
Description: Scaffold a `frontend/` React app (Vite recommended) with a test runner (Vitest + Testing Library). Render a placeholder "JobMatch AI" heading on the root page. Add one test that renders the app and asserts the heading appears, and confirm `npm test` passes.

## 3. Docker Compose for local dev
Goal: One `docker-compose up` brings up backend and frontend containers.
Description: Write a `docker-compose.yml` with two services — `backend` (FastAPI dev server) and `frontend` (React dev server) — plus their Dockerfiles. Wire ports and volume mounts for live reload. Supabase is external, so no DB container; the compose file only needs to read env vars, not define them.

## 4. Environment and secrets configuration
Goal: Centralize API keys and connection strings via `.env`.
Description: Create a `.env.example` listing all required variables (Adzuna app id/key, Jooble key, OpenAI key, Supabase URL/service key). Add backend settings loading (e.g. pydantic-settings) that reads these and fails fast with a clear message if a required one is missing. Do not commit real secrets; ensure `.env` is gitignored.

## 5. Database schema and migrations
Goal: Create Supabase tables for Profile, Job, and ApplicationStatus.
Description: Write SQL (or a migration file) defining the three tables from the plan's data model, including a unique constraint on `(source, external_id)` for jobs to support dedup, and a status-history representation for applications. Document how to apply it to a Supabase project. Deliverable is the schema plus apply instructions, not application code.

## 6. Backend database connection layer
Goal: Provide a reusable, tested way for the backend to talk to Supabase Postgres.
Description: Add a database client/session module that connects using the Supabase connection string from settings, and expose a simple query helper or session dependency for FastAPI routes. Include a test that verifies connection wiring (against a test/local Postgres or a mocked client). Assumes the schema from Task 5 but should not depend on it existing to run its test.

## 7. Profile model and CRUD endpoints
Goal: Store and retrieve the single user profile.
Description: Define the Profile shape (skills, seniority, locations, salary range, target titles, preferences) and add endpoints to create/read/update it. Since this is a single-user tool, a single profile row is sufficient. Cover the endpoints with request/response tests using stubbed persistence.

## 8. Adzuna API client
Goal: Fetch Canadian job listings from Adzuna.
Description: Implement a client that queries Adzuna's Canada endpoint for a given job title, returning raw results. Read credentials from settings, handle pagination for one page, and gracefully surface API errors. Test against a recorded/mocked HTTP response — no live network calls in tests.

## 9. Jooble API client
Goal: Fetch Canadian job listings from Jooble.
Description: Implement a client that queries Jooble with `country=CA` for a given job title and returns raw results. Read the key from settings and handle error responses. Test against a mocked HTTP response.

## 10. Normalize source results into the Job model
Goal: Map raw Adzuna/Jooble payloads to one canonical Job shape.
Description: Write pure functions that convert each source's raw listing into a common `Job` (source, external_id, title, company, location, salary, description, url). Handle missing/optional fields consistently. Unit-test the mappers with sample payloads from each source; no network or DB needed.

## 11. Job persistence with dedup
Goal: Save normalized jobs without creating duplicates.
Description: Add a function that upserts `Job` records keyed on `(source, external_id)`, setting `date_fetched` and leaving score fields null. Ensure re-fetching the same listing does not create a second row. Test the dedup behavior against a test database or mocked repository. Assumes the canonical Job shape from Task 10.

## 12. Pass 1 weighted scoring engine
Goal: Compute a 0–100 match score for a job against the profile.
Description: Implement pure scoring logic combining skills overlap (40%), seniority match (20%), location/remote fit (20%), and salary overlap (20%). Input is a Job plus a Profile; output is the composite score and per-component breakdown. Fully unit-tested with no external dependencies.

## 13. Pass 2 OpenAI re-ranking
Goal: Generate a compatibility rationale for top-scored jobs.
Description: Add a function that takes the top N (15–20) scored jobs plus the profile, calls the OpenAI API to produce a short human-readable rationale and an LLM score per job, and returns them. Read the key from settings and mock the OpenAI call in tests. Handle API failures without crashing the caller.

## 14. Fetch orchestration endpoint
Goal: One `POST /fetch` runs the full pipeline on demand.
Description: Wire together source clients → normalization → persistence → Pass 1 scoring → Pass 2 re-ranking into a single endpoint that returns a summary (counts fetched, new, scored). Compose the pieces behind interfaces so each can be stubbed. Test the orchestration flow with mocked collaborators.

## 15. Daily scheduled fetch
Goal: Automatically run the fetch pipeline once per day while running.
Description: Add APScheduler (or equivalent) inside the FastAPI backend to trigger the same fetch logic used by `POST /fetch` on a daily cadence. Make the schedule configurable and ensure it starts with the app and shuts down cleanly. Test that the job is registered and invokes the fetch callable; do not run real fetches in tests.

## 16. Jobs list endpoint with filters
Goal: Serve ranked jobs to the dashboard with filtering.
Description: Add `GET /jobs` returning jobs ordered by score, supporting query filters for score threshold, source, date fetched, and status. Include the score and LLM rationale in the response. Test filtering and ordering with seeded/mocked data.

## 17. Application status tracking endpoints
Goal: Track and update per-job application status and notes.
Description: Add endpoints to set a job's status (New → Saved → Applied → Interviewing → Rejected/Offer), append to its status history with timestamps, and edit a freeform notes field. Validate status transitions loosely (any status allowed, but recorded in history). Test the status update and history-append behavior.

## 18. Frontend: profile form
Goal: Let the user view and edit their profile in the UI.
Description: Build a React form for skills (tags), seniority, locations, salary range, and target titles, wired to the profile endpoints from Task 7. Show validation and a save confirmation. Assume the profile API shape; mock it in tests. Cover render and submit with a component test.

## 19. Frontend: job list and cards
Goal: Display ranked matches as a list/grid.
Description: Build a React view that fetches from `GET /jobs` and renders each job as a card showing title, company, location, salary, score, and LLM rationale, with a link to the listing. Handle loading and empty states. Test rendering against a mocked API response.

## 20. Frontend: filters bar
Goal: Let the user narrow the job list.
Description: Add UI controls for score threshold, source, date fetched, and status that drive the `GET /jobs` query params. Keep filter state in the URL or local state so it survives re-render. Test that changing a filter issues the expected request. Assumes the job list view from Task 19 but can be built against a stub.

## 21. Frontend: status tracking and notes
Goal: Let the user manage application status and notes per job.
Description: Add UI on each job card/detail to change status through the pipeline and edit notes, wired to the endpoints from Task 17, with optimistic or confirmed updates. Show current status and a simple history view. Test status change and notes edit against a mocked API.

## 22. Frontend: "Fetch new jobs now" button
Goal: Trigger an on-demand fetch from the dashboard.
Description: Add a button that calls `POST /fetch`, shows an in-progress state, and refreshes the job list on completion, surfacing the returned summary (e.g. "12 new jobs"). Handle and display errors. Test the click → request → refresh flow with a mocked API.
