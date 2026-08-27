"""Jobs router — exposes ``GET /jobs`` and ``POST /fetch``."""

from datetime import date
from typing import Any, Literal, cast

from fastapi import APIRouter, Depends, HTTPException, Query
from supabase import Client

from app import pipeline
from app.db import get_db
from app.models import JobOut, JobsResponse, Profile

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
    limit: int = Query(default=50, ge=0),
    offset: int = Query(default=0, ge=0),
    db: Client = Depends(get_db),  # noqa: B008
) -> JobsResponse:
    """Return a paginated, filtered, scored-descending list of jobs.

    Filters applied server-side (DB level):
    - ``min_score``: only jobs with raw_score >= min_score
    - ``source``: only jobs from the given source
    - ``since``: only jobs fetched on or after the given date

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
    query = db.table(_JOB_TABLE).select("*").gte("raw_score", min_score)

    if source is not None:
        query = query.eq("source", source)

    if since is not None:
        query = query.gte("date_fetched", since.isoformat())

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
        )
        for j in page
    ]

    return JobsResponse(total=total, jobs=jobs_out)


@router.post("/fetch")
async def fetch_jobs(db: Client = Depends(get_db)) -> dict[str, object]:  # noqa: B008
    """Trigger the full fetch → normalize → score → re-rank pipeline.

    Reads the stored profile from the database, then runs the pipeline which:
    - Fetches listings from Adzuna and Jooble in parallel
    - Normalizes and upserts results (dedup on source + external_id)
    - Scores all jobs with Pass 1
    - Re-ranks the top 20 with Pass 2 (OpenAI)
    - Persists llm_score and llm_rationale back to the job table

    Returns:
        A summary dict: ``{"fetched": N, "fetched_by_source": {"adzuna": N, "jooble": M},
        "window_days": K, "new": M, "scored": K}``

    Raises:
        404: No profile has been saved yet.
    """
    # Load the profile — required for scoring
    result = db.table(_PROFILE_TABLE).select("*").execute()
    rows = result.data
    if not rows:
        raise HTTPException(
            status_code=404,
            detail="Profile not found — save a profile before fetching",
        )

    row = _row_to_dict(rows[0])
    profile = Profile(**{k: v for k, v in row.items() if k != "id"})

    # Run the full pipeline — Pass 2 failures are handled internally and
    # will not cause a 500; the endpoint always returns a valid summary.
    summary = await pipeline.run(profile, db)
    return summary
