"""Jobs router — exposes ``POST /fetch`` to trigger the full pipeline."""

from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException
from supabase import Client

from app import pipeline
from app.db import get_db
from app.models import Profile

router = APIRouter()

_PROFILE_TABLE = "profile"


def _row_to_dict(row: Any) -> dict[str, Any]:
    """Cast a Supabase JSON row (typed loosely) to a plain dict."""
    return cast(dict[str, Any], row)


@router.post("/fetch")
async def fetch_jobs(db: Client = Depends(get_db)) -> dict[str, int]:  # noqa: B008
    """Trigger the full fetch → normalize → score → re-rank pipeline.

    Reads the stored profile from the database, then runs the pipeline which:
    - Fetches listings from Adzuna and Jooble in parallel
    - Normalizes and upserts results (dedup on source + external_id)
    - Scores all jobs with Pass 1
    - Re-ranks the top 20 with Pass 2 (OpenAI)
    - Persists llm_score and llm_rationale back to the job table

    Returns:
        A summary dict: ``{"fetched": N, "new": M, "scored": K}``

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
