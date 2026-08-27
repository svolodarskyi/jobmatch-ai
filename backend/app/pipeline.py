"""Pipeline helpers for persisting normalized Job records to the database.

This module owns the persistence step of the fetch → normalize → persist
pipeline.  Scoring (Pass 1 and Pass 2) lives in ``app/scoring/``.
"""

import asyncio
import logging
import time
from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any, TypedDict, cast

from postgrest.types import CountMethod
from supabase import Client

from app.models import Profile
from app.scoring import pass1, pass2
from app.settings import settings
from app.sources import adzuna, jooble
from app.sources.normalize import Job, normalize_adzuna, normalize_jooble

logger = logging.getLogger(__name__)


class _PersistResult(TypedDict):
    new_total: int
    updated_total: int
    new: dict[str, int]
    updated: dict[str, int]


def persist_jobs(jobs: list[Job], db: Client) -> _PersistResult:
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
        A dict with keys:
        - ``new_total``: total number of newly inserted rows across all sources.
        - ``updated_total``: total number of updated rows across all sources.
        - ``new``: per-source new counts, e.g. ``{"adzuna": N, "jooble": M}``.
        - ``updated``: per-source updated counts.
        Returns zero totals for an empty list.
    """
    if not jobs:
        return _PersistResult(new_total=0, updated_total=0, new={}, updated={})

    # Fetch existing (source, external_id) pairs in one query to classify each
    # job as new or updated without N individual look-ups.
    existing_result = (
        db.table("job").select("source,external_id").execute()
    )
    existing_keys: set[tuple[str, str]] = set()
    if existing_result.data:
        for row in existing_result.data:
            r = cast(dict[str, Any], row)
            existing_keys.add((str(r["source"]), str(r["external_id"])))

    new_by_source: dict[str, int] = {}
    updated_by_source: dict[str, int] = {}

    now = datetime.now(UTC).isoformat()

    for job in jobs:
        key = (job.source, job.external_id)
        if key in existing_keys:
            updated_by_source[job.source] = updated_by_source.get(job.source, 0) + 1
        else:
            new_by_source[job.source] = new_by_source.get(job.source, 0) + 1

        row = asdict(job)
        row["date_fetched"] = now
        # Scoring fields are intentionally omitted — left NULL by the DB default.
        db.table("job").upsert(row, on_conflict="source,external_id").execute()

    new_total = sum(new_by_source.values())
    updated_total = sum(updated_by_source.values())

    return _PersistResult(
        new_total=new_total,
        updated_total=updated_total,
        new=new_by_source,
        updated=updated_by_source,
    )


async def run(profile: Profile, db: Client) -> dict[str, object]:
    """Orchestrate the full fetch → normalize → persist → score → re-rank pipeline.

    Steps:
    1. Detect first run by counting existing job rows; select the appropriate
       fetch window (``FETCH_INITIAL_DAYS`` on first run, ``FETCH_INCREMENTAL_DAYS``
       on subsequent runs).
    2. Open a ``fetch_run`` row in the DB (records start time).
    3. Fetch raw listings from Adzuna and Jooble in parallel for each
       target title in the profile.
    4. Normalize all raw results into canonical ``Job`` instances.
    5. Persist (upsert/dedup) all jobs and record new vs. updated counts.
    6. Score every job with Pass 1 (pure function, no I/O).
    7. Pass the top 20 Pass 1 results to Pass 2 (OpenAI re-ranking).
    8. Persist ``llm_score`` and ``llm_rationale`` back to the ``job`` table.
    9. Update the ``fetch_run`` row with final stats.

    Args:
        profile: The user's ``Profile`` instance.
        db:      Injected Supabase client.

    Returns:
        A summary dict with keys:
        - ``fetched``: total raw listings retrieved
        - ``fetched_by_source``: ``{"adzuna": N, "jooble": M}``
        - ``window_days``: the fetch window used (days)
        - ``new``: number of newly inserted rows
        - ``updated``: number of updated rows
        - ``scored``: number of jobs that completed Pass 2
        - ``tokens_in``: total prompt tokens consumed by Pass 2
        - ``tokens_out``: total completion tokens produced by Pass 2
        - ``cost_usd``: estimated cost (gpt-4o-mini pricing)
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
    # Step 2: Open a fetch_run row to record pipeline instrumentation
    # ------------------------------------------------------------------
    run_result = db.table("fetch_run").insert(
        {"status": "ok", "window_days": max_days_old}
    ).execute()
    run_id: str | None = None
    if run_result.data:
        first_row = cast(dict[str, Any], run_result.data[0])
        run_id = str(first_row["id"])

    # ------------------------------------------------------------------
    # Step 3: Fetch from both sources in parallel for all target titles
    # ------------------------------------------------------------------
    source_errors: list[str] = []

    async def _fetch_source(
        coros: list[Any], source_name: str
    ) -> list[list[dict[str, object]]]:
        """Run all per-title coroutines for one source; return empty on failure."""
        try:
            return list(await asyncio.gather(*coros))
        except Exception as exc:  # noqa: BLE001
            msg = f"{source_name} fetch failed: {exc}"
            logger.warning(msg)
            source_errors.append(msg)
            return [[] for _ in coros]

    if titles:
        adzuna_batches, jooble_batches = await asyncio.gather(
            _fetch_source(
                [adzuna.fetch_jobs(t, max_days_old) for t in titles], "Adzuna"
            ),
            _fetch_source([jooble.fetch_jobs(t) for t in titles], "Jooble"),
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
    # Step 4: Normalize
    # ------------------------------------------------------------------
    normalized: list[Job] = []
    for raw in raw_adzuna:
        normalized.append(normalize_adzuna(raw))
    for raw in raw_jooble:
        job = normalize_jooble(raw, max_days_old)
        if job is not None:
            normalized.append(job)

    # ------------------------------------------------------------------
    # Step 5: Persist (upsert / dedup)
    # ------------------------------------------------------------------
    persist_result = persist_jobs(normalized, db)
    new_total: int = persist_result["new_total"]
    updated_total: int = persist_result["updated_total"]
    new_by_source: dict[str, int] = persist_result["new"]
    updated_by_source: dict[str, int] = persist_result["updated"]
    logger.info("Persisted: %d new, %d updated", new_total, updated_total)

    # ------------------------------------------------------------------
    # Step 6: Pass 1 scoring (pure, no I/O)
    # ------------------------------------------------------------------
    scored: list[tuple[Job, dict[str, float]]] = [
        (job, pass1.score(job, profile)) for job in normalized
    ]
    logger.info("Pass 1: %d jobs scored", len(scored))

    # ------------------------------------------------------------------
    # Step 7: Pass 2 re-ranking (capped at 20 — cost-control invariant)
    # ------------------------------------------------------------------
    rerank_result = pass2.rerank(scored, profile, cap=20)
    ranked = rerank_result.jobs
    tokens_in = rerank_result.tokens_in
    tokens_out = rerank_result.tokens_out
    logger.info("Pass 2: %d jobs scored", len(ranked))

    # ------------------------------------------------------------------
    # Step 8: Persist llm_score and llm_rationale back to DB
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

    # ------------------------------------------------------------------
    # Step 9: Update the fetch_run row with final stats
    # ------------------------------------------------------------------
    cost_usd = round((tokens_in * 0.15 + tokens_out * 0.60) / 1_000_000, 6)
    any_pass2_failed = any(r.llm_score is None for r in ranked)
    run_status = "partial" if (any_pass2_failed or source_errors) else "ok"

    # Build per-source stats for the jsonb column.
    source_stats: dict[str, dict[str, int]] = {}
    for src in set(list(new_by_source.keys()) + list(updated_by_source.keys())):
        source_stats[src] = {
            "new": new_by_source.get(src, 0),
            "updated": updated_by_source.get(src, 0),
        }

    if run_id is not None:
        db.table("fetch_run").update(
            {
                "completed_at": datetime.now(UTC).isoformat(),
                "fetched_total": total_raw,
                "new_jobs": new_total,
                "updated_jobs": updated_total,
                "scored_pass1": len(scored),
                "scored_pass2": len(ranked),
                "source_stats": source_stats,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "cost_usd": cost_usd,
                "status": run_status,
                "error_message": "; ".join(source_errors) if source_errors else None,
            }
        ).eq("id", run_id).execute()

    return {
        "fetched": total_raw,
        "fetched_by_source": {"adzuna": len(raw_adzuna), "jooble": len(raw_jooble)},
        "window_days": max_days_old,
        "new": new_total,
        "updated": updated_total,
        "scored": len(ranked),
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "cost_usd": cost_usd,
    }
