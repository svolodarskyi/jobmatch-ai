from datetime import datetime

from pydantic import BaseModel


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
