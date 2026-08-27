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
