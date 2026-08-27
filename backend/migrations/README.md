# Database Migrations

Plain SQL migrations for the JobMatch AI Supabase (Postgres 15) database.
No migration runner — apply manually.

## Files

| File | Description |
|---|---|
| `001_initial_schema.sql` | Creates `profile`, `job`, and `application_status` tables |

## How to apply

### Option 1 — Supabase SQL Editor (recommended for first-time setup)

1. Open your Supabase project at [https://supabase.com](https://supabase.com).
2. Go to **SQL Editor** in the left sidebar.
3. Paste the full contents of the migration file.
4. Click **Run**.

### Option 2 — psql

Use the full Postgres connection URI from your Supabase project settings
(**Settings → Database → Connection string → URI**).

```bash
psql "$SUPABASE_URL" -f backend/migrations/001_initial_schema.sql
```

> `SUPABASE_URL` here must be the `postgres://...` URI, not the REST/API URL
> stored in `.env` for the backend. Check your Supabase project's
> **Settings → Database** page for the correct string.

## Idempotency

Every `CREATE TABLE` statement uses `IF NOT EXISTS`. Re-running a migration
against an already-provisioned project is safe and produces no errors.

## Verification

After applying, confirm the three tables appear in the Supabase **Table Editor**:

- `profile`
- `job`
- `application_status`

Check that `job` has the `uq_job_source_external_id` unique constraint on
`(source, external_id)` — visible under **Table Editor → job → Indexes**.
