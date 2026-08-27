# API

Base URL (local): `http://localhost:8000`

All request and response bodies are JSON. All timestamps are ISO 8601 UTC strings. Errors follow a consistent shape (see [Errors](#errors)).

---

## Health

### `GET /health`

Returns `200` when the backend is up.

```json
{ "status": "ok" }
```

---

## Profile

Single-user tool — there is exactly one profile row. No profile ID in the URL.

### `GET /profile`

Returns the current profile.

**Response 200**

```json
{
  "target_titles": ["Data Engineer", "Senior Data Engineer"],
  "skills": ["Azure", "Databricks", "Spark", "Python", "Airflow", "SQL", "ADF", "CI/CD"],
  "seniority": "Senior",
  "locations": ["Calgary AB", "Toronto ON"],
  "remote": "preferred",
  "salary_min": 100000,
  "salary_max": 150000,
  "preferences": "Prefer product-led companies; avoid pure consulting."
}
```

`remote` is one of `"required"`, `"preferred"`, `"no"`.

### `PUT /profile`

Replaces the profile. All fields required except `preferences`.

**Request body** — same shape as `GET /profile` response.

**Response 200** — the saved profile (same shape).

**Response 422** — validation error (see [Errors](#errors)).

---

## Jobs

### `GET /jobs`

Returns jobs ordered by score (descending). All query params are optional.

| Param | Type | Default | Description |
|---|---|---|---|
| `min_score` | int (0–100) | `0` | Exclude jobs with `raw_score` below this |
| `source` | `adzuna` \| `jooble` | — | Filter to one source |
| `status` | string | — | Filter by application status |
| `since` | ISO date | — | Only jobs fetched on or after this date |
| `limit` | int | `50` | Max results |
| `offset` | int | `0` | Pagination offset |

**Response 200**

```json
{
  "total": 142,
  "jobs": [
    {
      "id": "uuid",
      "source": "adzuna",
      "title": "Senior Data Engineer",
      "company": "Acme Corp",
      "location": "Calgary, AB",
      "salary_min": 110000,
      "salary_max": 140000,
      "url": "https://...",
      "date_fetched": "2026-08-26T14:00:00Z",
      "raw_score": 84,
      "llm_score": 78,
      "llm_rationale": "Strong skills match on Azure and Databricks. They want 5+ yrs leadership; your profile shows 2 — worth addressing in a cover letter.",
      "status": "New",
      "notes": ""
    }
  ]
}
```

`llm_score` and `llm_rationale` are `null` for jobs not yet re-ranked by Pass 2.
`salary_min` / `salary_max` are `null` when the listing did not include salary.

### `POST /fetch`

Triggers an on-demand fetch pipeline run (same logic as the daily scheduler).

**Request body** — empty `{}` or omitted.

**Response 200**

```json
{
  "fetched": 48,
  "new": 12,
  "updated": 3,
  "scored_pass1": 48,
  "scored_pass2": 15
}
```

`new` = listings not previously seen; `updated` = existing rows where metadata changed (title, salary, etc.).

**Response 503** — if a fetch is already in progress.

```json
{ "detail": "A fetch is already running." }
```

---

## Application Status

### `PATCH /jobs/{id}/status`

Updates the status for a job and appends to its history.

**Request body**

```json
{ "status": "Applied" }
```

Valid values: `"New"`, `"Saved"`, `"Applied"`, `"Interviewing"`, `"Rejected"`, `"Offer"`.

**Response 200**

```json
{
  "job_id": "uuid",
  "status": "Applied",
  "history": [
    { "status": "New",     "changed_at": "2026-08-24T09:00:00Z" },
    { "status": "Saved",   "changed_at": "2026-08-25T11:30:00Z" },
    { "status": "Applied", "changed_at": "2026-08-26T14:22:00Z" }
  ],
  "updated_at": "2026-08-26T14:22:00Z"
}
```

**Response 404** — job not found.

### `PATCH /jobs/{id}/notes`

Replaces the notes for a job.

**Request body**

```json
{ "notes": "Recruiter is Jane Smith. Follow up by Sept 5." }
```

**Response 200**

```json
{
  "job_id": "uuid",
  "notes": "Recruiter is Jane Smith. Follow up by Sept 5.",
  "updated_at": "2026-08-26T14:23:00Z"
}
```

**Response 404** — job not found.

---

## Errors

All error responses share this shape:

```json
{
  "detail": "Human-readable message"
}
```

FastAPI validation errors (422) follow FastAPI's default structure:

```json
{
  "detail": [
    { "loc": ["body", "status"], "msg": "value is not a valid enum value", "type": "type_error.enum" }
  ]
}
```

| Status | Meaning |
|---|---|
| 400 | Bad request — malformed input not caught by schema validation |
| 404 | Resource not found |
| 422 | Request body failed schema validation |
| 503 | Service temporarily unavailable (e.g. fetch already running) |

500 errors are not enumerated — surface the exception message in development (`DEBUG=true`) and return a generic message in production.

---

## Notes on design

- No auth. This is a single-user local tool.
- No `DELETE /jobs` — the history view relies on seeing everything ever fetched; jobs are never deleted, only their status changes.
- No `POST /profile` — the profile always exists (seeded on first run); only `PUT` to replace it.
- Scores are computed server-side and stored. The frontend never sends a score.
