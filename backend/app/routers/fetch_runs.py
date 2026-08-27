from typing import Any, cast

from fastapi import APIRouter, Depends, Query
from supabase import Client

from app.db import get_db
from app.models import FetchRunOut, FetchRunsResponse

router = APIRouter()


@router.get("", response_model=FetchRunsResponse)
def list_fetch_runs(
    limit: int = Query(default=30, ge=1, le=100),
    db: Client = Depends(get_db),  # noqa: B008
) -> FetchRunsResponse:
    result = (
        db.table("fetch_run")
        .select("*")
        .order("started_at", desc=True)
        .limit(limit)
        .execute()
    )
    runs = [FetchRunOut(**cast(dict[str, Any], row)) for row in (result.data or [])]
    return FetchRunsResponse(runs=runs)
