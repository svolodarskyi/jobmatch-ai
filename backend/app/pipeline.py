"""Pipeline helpers for persisting normalized Job records to the database.

This module owns the persistence step of the fetch → normalize → persist
pipeline.  Scoring (Pass 1 and Pass 2) lives in ``app/scoring/``.
"""

import asyncio
import logging
import time
from dataclasses import asdict
from datetime import UTC, datetime

from postgrest.types import CountMethod
from supabase import Client

from app.models import Profile
from app.scoring import pass1, pass2
from app.settings import settings
from app.sources import adzuna, jooble
from app.sources.normalize import Job, normalize_adzuna, normalize_jooble

logger = logging.getLogger(__name__)


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


async def run(profile: Profile, db: Client) -> dict[str, object]:
    """Orchestrate the full fetch → normalize → persist → score → re-rank pipeline.

    Steps:
    1. Detect first run by counting existing job rows; select the appropriate
       fetch window (``FETCH_INITIAL_DAYS`` on first run, ``FETCH_INCREMENTAL_DAYS``
       on subsequent runs).
    2. Fetch raw listings from Adzuna and Jooble in parallel for each
       target title in the profile.
    3. Normalize all raw results into canonical ``Job`` instances.
    4. Persist (upsert/dedup) all jobs and record the count of rows written.
    5. Score every job with Pass 1 (pure function, no I/O).
    6. Pass the top 20 Pass 1 results to Pass 2 (OpenAI re-ranking).
    7. Persist ``llm_score`` and ``llm_rationale`` back to the ``job`` table.

    Args:
        profile: The user's ``Profile`` instance.
        db:      Injected Supabase client.

    Returns:
        A summary dict with keys:
        - ``fetched``: total raw listings retrieved
        - ``fetched_by_source``: ``{"adzuna": N, "jooble": M}``
        - ``window_days``: the fetch window used (days)
        - ``new``: number of rows upserted by ``persist_jobs``
        - ``scored``: number of jobs that completed Pass 2
    """
    start_time = time.monotonic()
    titles = profile.target_titles or []

    # ------------------------------------------------------------------
    # Step 1: Detect first run — count existing job rows
    # ------------------------------------------------------------------
    count_result = db.table("job").select("id", count=CountMethod.exact).execute()
    existing_count = count_result.count if count_result.count is not None else 0
    if existing_count == 0:
        max_days_old = settings.FETCH_INITIAL_DAYS
        logger.info("Starting fetch — first run, window: %d days", max_days_old)
    else:
        max_days_old = settings.FETCH_INCREMENTAL_DAYS
        logger.info(
            "Starting fetch — %d existing rows, window: %d days",
            existing_count,
            max_days_old,
        )

    # ------------------------------------------------------------------
    # Step 2: Fetch from both sources in parallel for all target titles
    # ------------------------------------------------------------------
    # Build coroutines for each source × title combination and gather
    # them in two groups (adzuna / jooble) so both sources run concurrently.
    if titles:
        adzuna_batches, jooble_batches = await asyncio.gather(
            asyncio.gather(*[adzuna.fetch_jobs(t, max_days_old) for t in titles]),
            asyncio.gather(*[jooble.fetch_jobs(t) for t in titles]),
        )
    else:
        adzuna_batches = []
        jooble_batches = []

    # Flatten per-title results into a single list per source, logging per title
    raw_adzuna: list[dict[str, object]] = []
    for title, batch in zip(titles, adzuna_batches):
        logger.info("Adzuna '%s': %d listings", title, len(batch))
        raw_adzuna.extend(batch)

    raw_jooble: list[dict[str, object]] = []
    for title, batch in zip(titles, jooble_batches):
        logger.info("Jooble '%s': %d listings", title, len(batch))
        raw_jooble.extend(batch)

    total_raw = len(raw_adzuna) + len(raw_jooble)
    logger.info(
        "Total retrieved: %d (Adzuna: %d, Jooble: %d)",
        total_raw,
        len(raw_adzuna),
        len(raw_jooble),
    )

    # ------------------------------------------------------------------
    # Step 3: Normalize
    # ------------------------------------------------------------------
    normalized: list[Job] = []
    for raw in raw_adzuna:
        normalized.append(normalize_adzuna(raw))
    for raw in raw_jooble:
        job = normalize_jooble(raw, max_days_old)
        if job is not None:
            normalized.append(job)

    # ------------------------------------------------------------------
    # Step 4: Persist (upsert / dedup)
    # ------------------------------------------------------------------
    upserted_count = persist_jobs(normalized, db)
    logger.info("Persisted: %d new, %d updated", upserted_count, 0)

    # ------------------------------------------------------------------
    # Step 5: Pass 1 scoring (pure, no I/O)
    # ------------------------------------------------------------------
    scored: list[tuple[Job, dict[str, float]]] = [
        (job, pass1.score(job, profile)) for job in normalized
    ]
    logger.info("Pass 1: %d jobs scored", len(scored))

    # ------------------------------------------------------------------
    # Step 6: Pass 2 re-ranking (capped at 20 — cost-control invariant)
    # ------------------------------------------------------------------
    ranked = pass2.rerank(scored, profile, cap=20)
    logger.info("Pass 2: %d jobs scoped", len(ranked))

    # ------------------------------------------------------------------
    # Step 7: Persist llm_score and llm_rationale back to DB
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

    elapsed = time.monotonic() - start_time
    logger.info("Run complete in %.1fs", elapsed)

    return {
        "fetched": total_raw,
        "fetched_by_source": {"adzuna": len(raw_adzuna), "jooble": len(raw_jooble)},
        "window_days": max_days_old,
        "new": upserted_count,
        "scored": len(ranked),
    }
