from datetime import datetime
from typing import Literal

from pydantic import BaseModel

# Valid application status values
ApplicationStatus = Literal["New", "Saved", "Applied", "Interviewing", "Rejected", "Offer"]


class Profile(BaseModel):
    target_titles: list[str] = []
    skills: list[str] = []
    seniority: str | None = None
    locations: list[str] = []
    salary_min: int | None = None
    salary_max: int | None = None
    preferences: dict[str, object] = {}


class ProfileInDB(Profile):
    """Profile as stored in the DB — includes the server-managed uuid."""

    id: str


class JobOut(BaseModel):
    """A single job row merged with its application_status (if any)."""

    id: str
    source: str
    title: str
    company: str | None
    location: str | None
    salary_min: int | None
    salary_max: int | None
    url: str | None
    date_fetched: datetime | None
    raw_score: float | None
    llm_score: float | None
    llm_rationale: str | None
    status: str
    notes: str


class JobsResponse(BaseModel):
    """Paginated jobs list response."""

    total: int
    jobs: list[JobOut]


# ---------------------------------------------------------------------------
# Status endpoint models
# ---------------------------------------------------------------------------


class StatusHistoryEntry(BaseModel):
    """A single entry in the application status history."""

    status: str
    changed_at: str


class StatusUpdateRequest(BaseModel):
    """Request body for PATCH /jobs/{id}/status."""

    status: ApplicationStatus


class StatusUpdateResponse(BaseModel):
    """Response body for PATCH /jobs/{id}/status."""

    job_id: str
    status: str
    history: list[StatusHistoryEntry]
    updated_at: str


class NotesUpdateRequest(BaseModel):
    """Request body for PATCH /jobs/{id}/notes."""

    notes: str


class NotesUpdateResponse(BaseModel):
    """Response body for PATCH /jobs/{id}/notes."""

    job_id: str
    notes: str
    updated_at: str


# ---------------------------------------------------------------------------
# Fetch runs endpoint models
# ---------------------------------------------------------------------------


class FetchRunOut(BaseModel):
    id: str
    started_at: str | None = None
    completed_at: str | None = None
    window_days: int | None = None
    fetched_total: int | None = None
    new_jobs: int | None = None
    updated_jobs: int | None = None
    scored_pass1: int | None = None
    scored_pass2: int | None = None
    source_stats: dict[str, object] = {}
    tokens_in: int | None = None
    tokens_out: int | None = None
    cost_usd: float | None = None
    status: str = "ok"
    error_message: str | None = None


class FetchRunsResponse(BaseModel):
    runs: list[FetchRunOut]
