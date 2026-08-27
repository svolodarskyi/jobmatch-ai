-- =============================================================================
-- 001_initial_schema.sql
-- Creates the three core tables for JobMatch AI: profile, job, application_status
--
-- HOW TO APPLY
-- ------------
-- Option 1 — Supabase SQL editor:
--   1. Open your Supabase project → SQL Editor
--   2. Paste the entire contents of this file
--   3. Click "Run"
--
-- Option 2 — psql (requires the Supabase connection string):
--   psql "$SUPABASE_URL" -f 001_initial_schema.sql
--   (SUPABASE_URL must be the full postgres:// connection URI, not the REST URL)
--
-- This file is idempotent: re-running it on an already-provisioned project is safe.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- profile
-- Stores the single user's job-search profile.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS profile (
    id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    target_titles text[]      NOT NULL DEFAULT '{}',
    skills        text[]      NOT NULL DEFAULT '{}',
    seniority     text,
    locations     text[]      NOT NULL DEFAULT '{}',
    salary_min    int,
    salary_max    int,
    preferences   jsonb       NOT NULL DEFAULT '{}'
);

-- ---------------------------------------------------------------------------
-- job
-- One row per unique job listing fetched from a source.
-- UNIQUE (source, external_id) enforces the dedup invariant: re-fetching the
-- same listing from the same provider must never create a duplicate row.
--
-- llm_score and llm_rationale are nullable — they remain NULL until Pass 2
-- (OpenAI re-ranking) runs on the top 15–20 Pass 1 results.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS job (
    id             uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    source         text        NOT NULL,           -- 'adzuna' | 'jooble'
    external_id    text        NOT NULL,
    title          text,
    company        text,
    location       text,
    salary_min     int,
    salary_max     int,
    description    text,
    url            text,
    date_fetched   timestamptz NOT NULL DEFAULT now(),
    raw_score      numeric,                        -- Pass 1 composite (0–100)
    llm_score      numeric,                        -- Pass 2; NULL until re-ranked
    llm_rationale  text,                           -- Pass 2; NULL until re-ranked

    CONSTRAINT uq_job_source_external_id UNIQUE (source, external_id)
);

-- ---------------------------------------------------------------------------
-- application_status
-- Tracks the user's application progress for a job.
--
-- status valid values: New | Saved | Applied | Interviewing | Rejected | Offer
--
-- history is an append-only JSONB array of status-transition records:
--   [{"status": "New", "changed_at": "2024-01-01T00:00:00Z"}, ...]
-- Each element records the status value and the ISO-8601 UTC timestamp of
-- when the transition occurred. Append new entries; do not overwrite old ones.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS application_status (
    id          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id      uuid        NOT NULL REFERENCES job (id) ON DELETE CASCADE,
    status      text        NOT NULL DEFAULT 'New',
    notes       text,
    history     jsonb       NOT NULL DEFAULT '[]',
    updated_at  timestamptz NOT NULL DEFAULT now()
);
