from datetime import datetime
from typing import Literal

from pydantic import BaseModel

# Valid application status values
ApplicationStatus = Literal["New", "Saved", "Applied", "Interviewing", "Rejected", "Offer"]

# Valid fetch_run status values
FetchRunStatus = Literal["running", "ok", "partial", "error"]


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


class StatusHistoryEntry(BaseModel):
    """A single entry in the application status history."""

    status: str
    changed_at: str


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
    fits_me: bool
    status_history: list[StatusHistoryEntry]


class JobsResponse(BaseModel):
    """Paginated jobs list response."""

    total: int
    jobs: list[JobOut]


# ---------------------------------------------------------------------------
# Status endpoint models
# ---------------------------------------------------------------------------


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


class FitsMeUpdateRequest(BaseModel):
    """Request body for PATCH /jobs/{id}/fits_me."""

    fits_me: bool


class FitsMeUpdateResponse(BaseModel):
    """Response body for PATCH /jobs/{id}/fits_me."""

    job_id: str
    fits_me: bool


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
    # Per-source stats keyed by source name (e.g. "adzuna", "jooble").
    # Each value has the fixed shape {"retrieved": int, "new": int, "updated": int}:
    #   - retrieved: raw listing count returned by that source before
    #     normalization/dedup, independent of how many turned out new,
    #     updated, or duplicate.
    #   - new: number of listings from that source newly inserted.
    #   - updated: number of listings from that source that updated an
    #     existing row.
    # Every source that was queried (profile.target_titles non-empty) gets
    # an entry, even if it retrieved 0 listings, produced 0 new/updated
    # jobs, or its fetch raised an exception (in which case its entry is
    # {"retrieved": 0, "new": 0, "updated": 0}). When no fetch was
    # attempted, this dict is empty. Typed as dict[str, object] rather than
    # a nested model to keep the jsonb column's shape flexible.
    source_stats: dict[str, object] = {}
    tokens_in: int | None = None
    tokens_out: int | None = None
    cost_usd: float | None = None
    status: FetchRunStatus
    error_message: str | None = None


class FetchRunsResponse(BaseModel):
    runs: list[FetchRunOut]
