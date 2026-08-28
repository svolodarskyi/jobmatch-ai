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

### `GET /fetch-runs`

Returns fetch-pipeline run history, most recent first.

| Param | Type | Default | Description |
|---|---|---|---|
| `limit` | int (1–100) | `30` | Max runs to return |

Results are ordered by `started_at` descending.

**Response 200**

```json
{
  "runs": [
    {
      "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "started_at": "2026-08-27T09:00:00Z",
      "completed_at": "2026-08-27T09:02:14Z",
      "window_days": 7,
      "fetched_total": 213,
      "new_jobs": 18,
      "updated_jobs": 4,
      "scored_pass1": 213,
      "scored_pass2": 18,
      "source_stats": {
        "adzuna": { "retrieved": 140, "new": 11, "updated": 2 },
        "jooble": { "retrieved": 73, "new": 7, "updated": 2 }
      },
      "tokens_in": 9820,
      "tokens_out": 3110,
      "cost_usd": 0.14,
      "status": "ok",
      "error_message": null
    }
  ]
}
```

| Field | Type | Description |
|---|---|---|
| `id` | string | Fetch run row id |
| `started_at` | ISO 8601 string \| `null` | When the run began |
| `completed_at` | ISO 8601 string \| `null` | When the run finished; `null` while still in progress (see caveat below) |
| `window_days` | int \| `null` | Lookback window used for the run |
| `fetched_total` | int \| `null` | Total listings fetched across all sources |
| `new_jobs` | int \| `null` | Listings newly inserted |
| `updated_jobs` | int \| `null` | Listings that updated an existing row |
| `scored_pass1` | int \| `null` | Jobs scored by the Pass 1 pure-function scorer |
| `scored_pass2` | int \| `null` | Jobs re-ranked by the Pass 2 OpenAI step |
| `source_stats` | object | Per-source stats, keyed by source name (`"adzuna"`, `"jooble"`) — see below |
| `tokens_in` | int \| `null` | Pass 2 prompt tokens consumed |
| `tokens_out` | int \| `null` | Pass 2 completion tokens consumed |
| `cost_usd` | float \| `null` | Estimated Pass 2 OpenAI cost for the run |
| `status` | string | One of `"ok"`, `"partial"`, `"error"` — see below |
| `error_message` | string \| `null` | See below |

**`source_stats` shape** — each value is `{"retrieved": int, "new": int, "updated": int}`:

- `retrieved` — raw listing count returned by that source before normalization/dedup.
- `new` — listings from that source newly inserted.
- `updated` — listings from that source that updated an existing row.

Every source that was queried (i.e. `profile.target_titles` is non-empty) gets an entry, even if it retrieved 0 listings or its fetch raised an exception — in both cases the entry is `{"retrieved": 0, "new": 0, "updated": 0}`. `source_stats` is `{}` only when no fetch was attempted at all (empty `target_titles`).

**`status` values:**

- `"ok"` — the run completed cleanly.
- `"partial"` — a source fetch failed or a Pass 2 rerank failed, but the pipeline otherwise completed (non-fatal).
- `"error"` — an unhandled exception escaped the pipeline.

**`error_message`:** `null` when `status` is `"ok"`; `str(exception)` when `status` is `"error"`. When `status` is `"partial"`, `error_message` depends on *why* it's partial — a `"partial"` run can be caused by a source-fetch failure, a Pass 2 (OpenAI) scoring failure, or both, and only the first populates `error_message`:

- Source-fetch failure (one or more sources raised during fetch): `error_message` is a `"; "`-joined summary of the per-source failure messages.
- Pass 2 scoring failure only (an OpenAI re-rank call failed for one of the capped top jobs, with no source-fetch failures): `error_message` is `null`. The failure is recorded only on the affected job row (`llm_score: null`, `llm_rationale: null`) — the fetch-run row itself carries no message for this case. So `status: "partial"` with `error_message: null` does not necessarily mean the run "still succeeded"; it can mean a Pass 2 failure occurred and left no trace here.

**In-progress caveat:** a `fetch_run` row is inserted with `status: "ok"` and `completed_at: null` before the run finishes, and only updated to its final `status`/`completed_at` once the pipeline completes. This means `"ok"` with `completed_at: null` currently means the run is **still running**, not that it succeeded — it is indistinguishable from a genuinely completed `"ok"` run except by the `null` `completed_at`. This ambiguity is tracked for a fix in #50; the behavior described here is current, pre-#50 behavior.

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

### `PATCH /jobs/{id}/fits_me`

Sets the `fits_me` flag for a job — a manual, user-set annotation independent of application-status tracking.

**Request body**

```json
{ "fits_me": true }
```

`fits_me` is a required bool.

**Response 200**

```json
{
  "job_id": "uuid",
  "fits_me": true
}
```

Note: unlike `.../status` and `.../notes`, this response has **no `updated_at` field**. This endpoint writes directly to the `job` table, not `application_status` — there is no shared "updated at" timestamp to report.

**Response 404** — job not found.

**Response 422** — request body missing `fits_me` or `fits_me` not a boolean.

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
