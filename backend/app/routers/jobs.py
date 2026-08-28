"""Jobs router — exposes ``GET /jobs`` and ``POST /fetch``."""

import logging
from datetime import date
from typing import Any, Literal, cast

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from supabase import Client

from app import pipeline
from app.db import get_client, get_db
from app.models import JobOut, JobsResponse, Profile

logger = logging.getLogger(__name__)

router = APIRouter()

_PROFILE_TABLE = "profile"
_JOB_TABLE = "job"
_STATUS_TABLE = "application_status"

_DEFAULT_STATUS = "New"
_DEFAULT_NOTES = ""


def _row_to_dict(row: Any) -> dict[str, Any]:
    """Cast a Supabase JSON row (typed loosely) to a plain dict."""
    return cast(dict[str, Any], row)


@router.get("/", response_model=JobsResponse)
def list_jobs(
    min_score: int = Query(default=0, ge=0, le=100),
    source: Literal["adzuna", "jooble"] | None = Query(default=None),
    status: str | None = Query(default=None),
    since: date | None = Query(default=None),  # noqa: B008
    fits_me: bool | None = Query(default=None),
    limit: int = Query(default=50, ge=0),
    offset: int = Query(default=0, ge=0),
    db: Client = Depends(get_db),  # noqa: B008
) -> JobsResponse:
    """Return a paginated, filtered, scored-descending list of jobs.

    Filters applied server-side (DB level):
    - ``min_score``: only jobs with raw_score >= min_score. ``min_score=0``
      (the default, and indistinguishable from an omitted param) applies no
      raw_score filter at all, so unscored jobs (``raw_score IS NULL``) are
      included alongside scored ones. Any ``min_score > 0`` applies a plain
      ``.gte`` filter, which — per Postgres NULL comparison semantics —
      naturally excludes ``raw_score IS NULL`` rows.
    - ``source``: only jobs from the given source
    - ``since``: only jobs fetched on or after the given date
    - ``fits_me``: only jobs with the given fits_me flag; omitted means no
      filtering on the flag (behavior unchanged from before this field
      existed)

    Filters applied in Python (after merging application_status):
    - ``status``: filter by application status; "New" matches both explicit
      "New" rows *and* jobs with no application_status row at all.

    Returns:
        ``{"total": N, "jobs": [...]}`` where ``total`` is unaffected by
        ``limit``/``offset`` (reflects the full filtered count).
    """
    # ------------------------------------------------------------------
    # 1. Fetch jobs from DB with DB-level filters
    # ------------------------------------------------------------------
    query = db.table(_JOB_TABLE).select("*")

    if min_score > 0:
        # Explicit non-zero threshold: only jobs that demonstrated a score
        # of at least min_score. NULL raw_score rows are excluded because
        # `NULL >= N` is never true in Postgres.
        query = query.gte("raw_score", min_score)
    # else: min_score is 0 (explicit or omitted — indistinguishable per
    # FastAPI's Query(default=0, ...)). Apply no raw_score filter, so both
    # scored and unscored (raw_score IS NULL) rows come back.

    if source is not None:
        query = query.eq("source", source)

    if since is not None:
        query = query.gte("date_fetched", since.isoformat())

    if fits_me is not None:
        query = query.eq("fits_me", fits_me)

    job_result = query.execute()
    job_rows: list[dict[str, Any]] = [_row_to_dict(r) for r in (job_result.data or [])]

    if not job_rows:
        return JobsResponse(total=0, jobs=[])

    # ------------------------------------------------------------------
    # 2. Fetch application_status rows for these jobs
    # ------------------------------------------------------------------
    job_ids = [r["id"] for r in job_rows]

    status_result = (
        db.table(_STATUS_TABLE).select("*").in_("job_id", job_ids).execute()
    )
    status_by_job: dict[str, dict[str, Any]] = {}
    for row in status_result.data or []:
        s = _row_to_dict(row)
        status_by_job[s["job_id"]] = s

    # ------------------------------------------------------------------
    # 3. Merge: attach status/notes, apply status filter
    # ------------------------------------------------------------------
    merged: list[dict[str, Any]] = []
    for job in job_rows:
        app_row = status_by_job.get(job["id"])
        job_status = app_row["status"] if app_row else _DEFAULT_STATUS
        job_notes = app_row["notes"] if app_row else _DEFAULT_NOTES
        job["status"] = job_status
        job["notes"] = job_notes

        # Apply Python-level status filter
        if status is not None:
            if status == _DEFAULT_STATUS:
                # "New" matches explicit "New" rows AND jobs with no row
                if job_status != _DEFAULT_STATUS:
                    continue
            else:
                if job_status != status:
                    continue

        merged.append(job)

    # ------------------------------------------------------------------
    # 4. Sort: raw_score DESC, id ASC (deterministic tiebreak)
    # ------------------------------------------------------------------
    merged.sort(key=lambda j: (-(j.get("raw_score") or 0), j["id"]))

    # ------------------------------------------------------------------
    # 5. Total count (before pagination)
    # ------------------------------------------------------------------
    total = len(merged)

    # ------------------------------------------------------------------
    # 6. Paginate
    # ------------------------------------------------------------------
    page = merged[offset : offset + limit]

    jobs_out = [
        JobOut(
            id=j["id"],
            source=j["source"],
            title=j["title"],
            company=j.get("company"),
            location=j.get("location"),
            salary_min=j.get("salary_min"),
            salary_max=j.get("salary_max"),
            url=j.get("url"),
            date_fetched=j.get("date_fetched"),
            raw_score=j.get("raw_score"),
            llm_score=j.get("llm_score"),
            llm_rationale=j.get("llm_rationale"),
            status=j["status"],
            notes=j["notes"],
            fits_me=j.get("fits_me", False),
        )
        for j in page
    ]

    return JobsResponse(total=total, jobs=jobs_out)


async def _run_pipeline_bg(profile: Profile) -> None:
    """Background task wrapper — gets its own DB client so it outlives the request."""
    db = get_client()
    try:
        await pipeline.run(profile, db)
    except Exception:
        logger.exception("Background pipeline run failed")


@router.post("/fetch", status_code=202)
async def fetch_jobs(
    background_tasks: BackgroundTasks,
    db: Client = Depends(get_db),  # noqa: B008
) -> dict[str, object]:
    """Kick off the fetch pipeline as a background task and return immediately.

    Reads the stored profile from the database, then enqueues the pipeline
    which runs asynchronously after the response is sent.  Poll
    ``GET /fetch-runs?limit=1`` to track progress.

    Returns:
        ``{"status": "started"}`` with HTTP 202.

    Raises:
        404: No profile has been saved yet.
    """
    result = db.table(_PROFILE_TABLE).select("*").execute()
    rows = result.data
    if not rows:
        raise HTTPException(
            status_code=404,
            detail="Profile not found — save a profile before fetching",
        )

    row = _row_to_dict(rows[0])
    profile = Profile(**{k: v for k, v in row.items() if k != "id"})

    background_tasks.add_task(_run_pipeline_bg, profile)
    return {"status": "started"}
