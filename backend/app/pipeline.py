"""Pipeline helpers for persisting normalized Job records to the database.

This module owns the persistence step of the fetch → normalize → persist
pipeline.  Scoring (Pass 1 and Pass 2) lives in ``app/scoring/``.
"""

import asyncio
from dataclasses import asdict
from datetime import UTC, datetime

from supabase import Client

from app.models import Profile
from app.scoring import pass1, pass2
from app.sources import adzuna, jooble
from app.sources.normalize import Job, normalize_adzuna, normalize_jooble


def persist_jobs(jobs: list[Job], db: Client) -> int:
    """Upsert a list of normalized Job records into the ``job`` table.

    Each job is keyed on ``(source, external_id)``.  A second call with the
    same job updates the existing row rather than creating a duplicate; the
    UNIQUE constraint on the table enforces this at the DB level, and this
    function uses ``upsert`` so Postgres resolves the conflict automatically.

    ``date_fetched`` is stamped to the current UTC time on every call.
    ``raw_score``, ``llm_score``, and ``llm_rationale`` are **not** set here;
    they remain NULL until the scoring passes run.

    Args:
        jobs: Normalized Job instances to persist.
        db:   Injected Supabase client (never imported directly, so tests can
              substitute a mock).

    Returns:
        The number of rows upserted (``len(jobs)``), or 0 for an empty list.
    """
    if not jobs:
        return 0

    now = datetime.now(UTC).isoformat()

    for job in jobs:
        row = asdict(job)
        row["date_fetched"] = now
        # Scoring fields are intentionally omitted — left NULL by the DB default.
        db.table("job").upsert(row, on_conflict="source,external_id").execute()

    return len(jobs)


async def run(profile: Profile, db: Client) -> dict[str, int]:
    """Orchestrate the full fetch → normalize → persist → score → re-rank pipeline.

    Steps:
    1. Fetch raw listings from Adzuna and Jooble in parallel for each
       target title in the profile.
    2. Normalize all raw results into canonical ``Job`` instances.
    3. Persist (upsert/dedup) all jobs and record the count of rows written.
    4. Score every job with Pass 1 (pure function, no I/O).
    5. Pass the top 20 Pass 1 results to Pass 2 (OpenAI re-ranking).
    6. Persist ``llm_score`` and ``llm_rationale`` back to the ``job`` table.

    Args:
        profile: The user's ``Profile`` instance.
        db:      Injected Supabase client.

    Returns:
        A summary dict: ``{"fetched": N, "new": M, "scored": K}`` where
        ``fetched`` is the total raw listings retrieved, ``new`` is the number
        of rows upserted by ``persist_jobs``, and ``scored`` is the number of
        jobs that completed Pass 2.
    """
    titles = profile.target_titles or []

    # ------------------------------------------------------------------
    # Step 1: Fetch from both sources in parallel for all target titles
    # ------------------------------------------------------------------
    # Build coroutines for each source × title combination and gather
    # them in two groups (adzuna / jooble) so both sources run concurrently.
    if titles:
        adzuna_batches, jooble_batches = await asyncio.gather(
            asyncio.gather(*[adzuna.fetch_jobs(t) for t in titles]),
            asyncio.gather(*[jooble.fetch_jobs(t) for t in titles]),
        )
    else:
        adzuna_batches = []
        jooble_batches = []

    # Flatten per-title results into a single list per source
    raw_adzuna: list[dict[str, object]] = []
    for batch in adzuna_batches:
        raw_adzuna.extend(batch)

    raw_jooble: list[dict[str, object]] = []
    for batch in jooble_batches:
        raw_jooble.extend(batch)

    total_raw = len(raw_adzuna) + len(raw_jooble)

    # ------------------------------------------------------------------
    # Step 2: Normalize
    # ------------------------------------------------------------------
    normalized: list[Job] = []
    for raw in raw_adzuna:
        normalized.append(normalize_adzuna(raw))
    for raw in raw_jooble:
        normalized.append(normalize_jooble(raw))

    # ------------------------------------------------------------------
    # Step 3: Persist (upsert / dedup)
    # ------------------------------------------------------------------
    upserted_count = persist_jobs(normalized, db)

    # ------------------------------------------------------------------
    # Step 4: Pass 1 scoring (pure, no I/O)
    # ------------------------------------------------------------------
    scored: list[tuple[Job, dict[str, float]]] = [
        (job, pass1.score(job, profile)) for job in normalized
    ]

    # ------------------------------------------------------------------
    # Step 5: Pass 2 re-ranking (capped at 20 — cost-control invariant)
    # ------------------------------------------------------------------
    ranked = pass2.rerank(scored, profile, cap=20)

    # ------------------------------------------------------------------
    # Step 6: Persist llm_score and llm_rationale back to DB
    # ------------------------------------------------------------------
    for ranked_job in ranked:
        if ranked_job.llm_score is not None or ranked_job.llm_rationale is not None:
            db.table("job").update(
                {
                    "llm_score": ranked_job.llm_score,
                    "llm_rationale": ranked_job.llm_rationale,
                }
            ).eq("source", ranked_job.job.source).eq(
                "external_id", ranked_job.job.external_id
            ).execute()

    return {
        "fetched": total_raw,
        "new": upserted_count,
        "scored": len(ranked),
    }
