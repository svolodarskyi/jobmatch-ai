from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException
from supabase import Client

from app.db import get_db
from app.models import Profile, ProfileInDB

router = APIRouter()

_TABLE = "profile"


def _row_to_dict(row: Any) -> dict[str, Any]:
    """Cast a Supabase JSON row (typed loosely) to a plain dict."""
    return cast(dict[str, Any], row)


@router.get("", response_model=ProfileInDB)
def get_profile(db: Client = Depends(get_db)) -> ProfileInDB:  # noqa: B008
    """Return the single user profile, or 404 if none has been saved yet."""
    result = db.table(_TABLE).select("*").execute()
    rows = result.data
    if not rows:
        raise HTTPException(status_code=404, detail="Profile not found")
    return ProfileInDB(**_row_to_dict(rows[0]))


@router.put("", response_model=ProfileInDB)
def upsert_profile(body: Profile, db: Client = Depends(get_db)) -> ProfileInDB:  # noqa: B008
    """Create or fully overwrite the single user profile."""
    # Use a fixed sentinel id so subsequent calls update the same row.
    FIXED_ID = "00000000-0000-0000-0000-000000000001"
    payload: dict[str, Any] = {
        "id": FIXED_ID,
        **body.model_dump(),
    }
    db.table(_TABLE).upsert(payload).execute()
    result = db.table(_TABLE).select("*").execute()
    rows = result.data
    if not rows:
        raise HTTPException(status_code=500, detail="Upsert succeeded but row not found")
    return ProfileInDB(**_row_to_dict(rows[0]))
