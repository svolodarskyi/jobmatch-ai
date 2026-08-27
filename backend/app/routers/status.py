"""Status router — exposes PATCH /jobs/{id}/status and PATCH /jobs/{id}/notes."""

from datetime import UTC, datetime
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException
from supabase import Client

from app.db import get_db
from app.models import (
    NotesUpdateRequest,
    NotesUpdateResponse,
    StatusHistoryEntry,
    StatusUpdateRequest,
    StatusUpdateResponse,
)

router = APIRouter()

_JOB_TABLE = "job"
_STATUS_TABLE = "application_status"


def _row_to_dict(row: Any) -> dict[str, Any]:
    """Cast a Supabase JSON row (typed loosely) to a plain dict."""
    return cast(dict[str, Any], row)


def _now_iso() -> str:
    """Return current UTC time as an ISO 8601 string."""
    return datetime.now(UTC).isoformat()


def _check_job_exists(job_id: str, db: Client) -> None:
    """Raise 404 if job_id is not found in the job table."""
    result = db.table(_JOB_TABLE).select("id").eq("id", job_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found")


def _fetch_status_row(job_id: str, db: Client) -> dict[str, Any] | None:
    """Return the existing application_status row for job_id, or None."""
    result = db.table(_STATUS_TABLE).select("*").eq("job_id", job_id).execute()
    rows = result.data or []
    if not rows:
        return None
    return _row_to_dict(rows[0])


@router.patch("/{job_id}/status", response_model=StatusUpdateResponse)
def update_status(
    job_id: str,
    body: StatusUpdateRequest,
    db: Client = Depends(get_db),  # noqa: B008
) -> StatusUpdateResponse:
    """Update the application status for a job.

    Appends a new history entry rather than overwriting. On first call, an
    application_status row is created (upsert). On subsequent calls, the
    existing history is preserved and the new status is appended.

    Returns the updated status, full history, and updated_at timestamp.

    Raises:
        404: The job_id does not exist in the job table.
        422: The status value is not one of the allowed enum values.
    """
    _check_job_exists(job_id, db)

    existing = _fetch_status_row(job_id, db)
    now = _now_iso()

    # Build history: carry over existing entries, then append new status
    existing_history: list[dict[str, Any]] = []
    if existing and existing.get("history"):
        existing_history = list(existing["history"])

    new_entry = {"status": body.status, "changed_at": now}
    updated_history = existing_history + [new_entry]

    db.table(_STATUS_TABLE).upsert(
        {
            "job_id": job_id,
            "status": body.status,
            "history": updated_history,
            "updated_at": now,
        },
        on_conflict="job_id",
    ).execute()

    history_out = [
        StatusHistoryEntry(status=entry["status"], changed_at=entry["changed_at"])
        for entry in updated_history
    ]

    return StatusUpdateResponse(
        job_id=job_id,
        status=body.status,
        history=history_out,
        updated_at=now,
    )


@router.patch("/{job_id}/notes", response_model=NotesUpdateResponse)
def update_notes(
    job_id: str,
    body: NotesUpdateRequest,
    db: Client = Depends(get_db),  # noqa: B008
) -> NotesUpdateResponse:
    """Update the notes for a job application.

    Does not touch the status or history fields. Creates the
    application_status row on first call (upsert).

    Returns the updated notes and updated_at timestamp.

    Raises:
        404: The job_id does not exist in the job table.
    """
    _check_job_exists(job_id, db)

    now = _now_iso()

    db.table(_STATUS_TABLE).upsert(
        {
            "job_id": job_id,
            "notes": body.notes,
            "updated_at": now,
        },
        on_conflict="job_id",
    ).execute()

    return NotesUpdateResponse(
        job_id=job_id,
        notes=body.notes,
        updated_at=now,
    )
