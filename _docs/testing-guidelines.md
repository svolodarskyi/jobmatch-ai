# Testing Guidelines

## Backend (pytest)

### Structure

```
backend/tests/
  conftest.py              # shared fixtures: app client, fake profile, sample jobs
  test_scoring_pass1.py    # pure unit tests — no fixtures needed
  test_scoring_pass2.py    # mocked OpenAI
  test_sources_adzuna.py   # mocked HTTP
  test_sources_jooble.py   # mocked HTTP
  test_normalize.py        # pure unit tests
  test_pipeline.py         # mocked collaborators
  test_routers_jobs.py     # TestClient, mocked DB
  test_routers_profile.py
  test_routers_status.py
```

### Rules

**No live network calls.** Every HTTP call to Adzuna, Jooble, or OpenAI must be intercepted. Use `respx` for HTTPX-based clients or `responses` for requests-based ones. Never rely on real API keys being present in the test environment.

**No production database.** `db.py` must be injectable. In tests, pass a mock session or stub repository. Never point tests at the real Supabase project.

**`pass1.py` has no dependencies** — test it with plain `assert` statements. No fixtures, no mocking.

**`pass2.py` tests mock the OpenAI call** and assert on how the result is used, not on the LLM's output. Test error paths (rate limit, timeout) as well as the happy path.

**Pipeline tests mock all collaborators** — Adzuna client, Jooble client, normalize, DB, pass1, pass2 are all stubs. The test verifies orchestration (call order, what gets persisted, what gets scored).

### Fixtures to define in `conftest.py`

```python
@pytest.fixture
def client():
    # FastAPI TestClient with DB dependency overridden

@pytest.fixture
def fake_profile():
    # Profile with known skills/seniority/locations/salary for deterministic scoring

@pytest.fixture
def sample_job():
    # One canonical Job with all fields populated

@pytest.fixture
def adzuna_raw_response():
    # Recorded JSON payload from Adzuna — load from tests/fixtures/adzuna_sample.json

@pytest.fixture
def jooble_raw_response():
    # Recorded JSON payload from Jooble — load from tests/fixtures/jooble_sample.json
```

Store recorded API payloads in `backend/tests/fixtures/` as `.json` files.

### Running tests

```bash
pytest                                      # all tests
pytest tests/test_scoring_pass1.py          # one file
pytest tests/test_scoring_pass1.py::test_skills_full_overlap  # one test
pytest -x                                   # stop on first failure
pytest --tb=short                           # concise tracebacks
```

---

## Frontend (Vitest + Testing Library)

### Structure

```
frontend/src/
  components/
    JobCard/
      JobCard.tsx
      JobCard.test.tsx      # co-located with component
  views/
    Dashboard/
      Dashboard.tsx
      Dashboard.test.tsx
```

### Rules

**Co-locate tests with components.** A test file lives next to the file it tests.

**Mock the API layer, not React internals.** Use `msw` (Mock Service Worker) to intercept `fetch` calls to `localhost:8000`. This keeps tests close to real browser behaviour. Set up MSW handlers in `src/mocks/handlers.ts` and start the server in `src/mocks/setup.ts`.

**Test behaviour, not implementation.** Query by role, label, or visible text — never by class name or component internals.

**Do not test that fetch was called.** Assert on what the user sees after data loads, not on whether a specific function was invoked.

**Filter state tests** should verify that changing a filter updates the URL query string or triggers the expected API request (captured by MSW), not that a setState was called.

### What to test per component

| Component | What to cover |
|---|---|
| `JobCard` | Renders title, company, score, rationale; status selector changes status on click |
| `Dashboard` | Shows cards for mocked jobs; empty state when list is empty; loading state |
| `FiltersBar` | Changing a filter issues a new `GET /jobs` request with correct params |
| `ProfileForm` | Submit fires `PUT /profile` with the form values; shows save confirmation |
| `FetchButton` | Click fires `POST /fetch`; shows in-progress; refreshes list on success; shows error on failure |

### Running tests

```bash
npm test            # watch mode
npm run test:run    # single pass (CI)
npm run test:run -- --reporter=verbose   # see every test name
```

---

## What does NOT need a test

- `settings.py` env-var loading — covered by fail-fast startup behaviour.
- Docker and compose config.
- SQL migrations — verified manually against Supabase before merge.
- APScheduler registration — test only that the callable is wired, not the scheduler internals.
