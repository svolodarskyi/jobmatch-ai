"""Pipeline helpers for persisting normalized Job records to the database.

This module owns the persistence step of the fetch → normalize → persist
pipeline.  Scoring (Pass 1 and Pass 2) lives in ``app/scoring/``.
"""

from dataclasses import asdict
from datetime import UTC, datetime

from supabase import Client

from app.sources.normalize import Job


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
