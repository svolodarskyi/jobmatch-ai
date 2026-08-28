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
| `min_score` | int (0–100) | `0` | Only include jobs with `raw_score >= min_score`. See note below on the `0` default. |
| `source` | `adzuna` \| `jooble` | — | Filter to one source |
| `status` | string | — | Filter by application status |
| `since` | ISO date | — | Only jobs fetched on or after this date |
| `fits_me` | bool | — | Filter to jobs with this fits_me value |
| `limit` | int | `50` | Max results |
| `offset` | int | `0` | Pagination offset |

`min_score=0` — the default, and indistinguishable from omitting the param entirely — applies **no** `raw_score` filter, so unscored jobs (`raw_score IS NULL`) are included alongside scored ones. Any `min_score > 0` applies a plain `raw_score >= min_score` filter, which (per Postgres NULL comparison semantics) naturally excludes `raw_score IS NULL` rows.

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
      "notes": "",
      "fits_me": false,
      "status_history": [
        { "status": "New", "changed_at": "2026-08-24T09:00:00Z" }
      ]
    }
  ]
}
```

`llm_score` and `llm_rationale` are `null` for jobs not yet re-ranked by Pass 2.
`salary_min` / `salary_max` are `null` when the listing did not include salary.
`status_history` is `[]` for a job with no application-status row yet; otherwise it mirrors the
`history` array returned by `PATCH /jobs/{id}/status`, oldest entry first.

### `POST /fetch`

Kicks off the fetch pipeline as a background task and returns immediately (same logic as the daily scheduler). The request handler only validates that a profile exists and enqueues the run — it does not wait for the pipeline to finish.

**Request body** — empty `{}` or omitted.

**Response 202**

```json
{ "status": "started" }
```

Poll `GET /fetch-runs?limit=1` to track progress of the run (fetched/new/updated counts, scoring counts, and completion status are recorded there, not in this response).

**Response 404** — no profile has been saved yet.

```json
{ "detail": "Profile not found — save a profile before fetching" }
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
