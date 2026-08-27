-- backend/migrations/002_fetch_run.sql
CREATE TABLE IF NOT EXISTS fetch_run (
    id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    started_at    timestamptz NOT NULL DEFAULT now(),
    completed_at  timestamptz,
    window_days   int,
    fetched_total int,
    new_jobs      int,
    updated_jobs  int,
    scored_pass1  int,
    scored_pass2  int,
    source_stats  jsonb       NOT NULL DEFAULT '{}',
    tokens_in     int,
    tokens_out    int,
    cost_usd      numeric(10, 6),
    status        text        NOT NULL DEFAULT 'ok',
    error_message text
);
