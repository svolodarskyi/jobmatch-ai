"""Unit tests for sources/normalize.py.

All tests are pure — no mocking, no network, no DB access.
Payloads are minimal inline dicts that mirror the structure of real API
responses from Adzuna and Jooble.
"""

from app.sources.normalize import Job, normalize_adzuna, normalize_jooble

# ---------------------------------------------------------------------------
# Adzuna
# ---------------------------------------------------------------------------

ADZUNA_FULL = {
    "id": "az-123",
    "title": "Senior Data Engineer",
    "company": {"display_name": "Acme Corp"},
    "location": {"display_name": "Toronto, Ontario"},
    "salary_min": 90000.0,
    "salary_max": 120000.0,
    "description": "Build and maintain data pipelines.",
    "redirect_url": "https://adzuna.ca/jobs/az-123",
}


def test_normalize_adzuna_full_payload():
    """Happy path: all nine canonical fields are populated."""
    job = normalize_adzuna(ADZUNA_FULL)

    assert isinstance(job, Job)
    assert job.source == "adzuna"
    assert job.external_id == "az-123"
    assert job.title == "Senior Data Engineer"
    assert job.company == "Acme Corp"
    assert job.location == "Toronto, Ontario"
    assert job.salary_min == 90000
    assert job.salary_max == 120000
    assert job.description == "Build and maintain data pipelines."
    assert job.url == "https://adzuna.ca/jobs/az-123"


def test_normalize_adzuna_salary_absent():
    """Partial payload: salary fields absent → salary_min/max are None."""
    raw = {**ADZUNA_FULL}
    raw.pop("salary_min", None)
    raw.pop("salary_max", None)

    job = normalize_adzuna(raw)

    assert job.salary_min is None
    assert job.salary_max is None


def test_normalize_adzuna_company_absent():
    """Partial payload: company key absent → company is None."""
    raw = {**ADZUNA_FULL}
    raw.pop("company", None)

    job = normalize_adzuna(raw)

    assert job.company is None


def test_normalize_adzuna_location_absent():
    """Partial payload: location key absent → location is None."""
    raw = {**ADZUNA_FULL}
    raw.pop("location", None)

    job = normalize_adzuna(raw)

    assert job.location is None


def test_normalize_adzuna_description_empty():
    """Partial payload: description absent → description is None."""
    raw = {**ADZUNA_FULL, "description": None}

    job = normalize_adzuna(raw)

    assert job.description is None


def test_normalize_adzuna_salary_cast_to_int():
    """Salary floats from Adzuna are cast to int."""
    raw = {**ADZUNA_FULL, "salary_min": 75500.99, "salary_max": 110000.5}

    job = normalize_adzuna(raw)

    assert job.salary_min == 75500
    assert job.salary_max == 110000
    assert isinstance(job.salary_min, int)
    assert isinstance(job.salary_max, int)


# ---------------------------------------------------------------------------
# Jooble
# ---------------------------------------------------------------------------

JOOBLE_FULL = {
    "id": "jb-456",
    "title": "Data Engineer",
    "company": "Globex Inc",
    "location": "Vancouver, BC",
    "salary": "95000",
    "snippet": "Work on distributed systems at scale.",
    "link": "https://jooble.org/jobs/jb-456",
}


def test_normalize_jooble_full_payload():
    """Happy path: all nine canonical fields are populated."""
    job = normalize_jooble(JOOBLE_FULL)

    assert isinstance(job, Job)
    assert job.source == "jooble"
    assert job.external_id == "jb-456"
    assert job.title == "Data Engineer"
    assert job.company == "Globex Inc"
    assert job.location == "Vancouver, BC"
    assert job.salary_min == 95000
    assert job.salary_max is None  # Jooble has no salary_max
    assert job.description == "Work on distributed systems at scale."
    assert job.url == "https://jooble.org/jobs/jb-456"


def test_normalize_jooble_snippet_absent():
    """Partial payload: snippet absent → description is None."""
    raw = {**JOOBLE_FULL}
    raw.pop("snippet", None)

    job = normalize_jooble(raw)

    assert job.description is None


def test_normalize_jooble_snippet_none():
    """Partial payload: snippet explicitly None → description is None."""
    raw = {**JOOBLE_FULL, "snippet": None}

    job = normalize_jooble(raw)

    assert job.description is None


def test_normalize_jooble_non_numeric_salary():
    """Non-numeric salary string → salary_min is None, no exception raised."""
    raw = {**JOOBLE_FULL, "salary": "$85,000 a year"}

    job = normalize_jooble(raw)

    assert job.salary_min is None
    assert job.salary_max is None


def test_normalize_jooble_salary_absent():
    """Partial payload: salary field absent → salary_min is None."""
    raw = {**JOOBLE_FULL}
    raw.pop("salary", None)

    job = normalize_jooble(raw)

    assert job.salary_min is None
    assert job.salary_max is None


def test_normalize_jooble_company_absent():
    """Partial payload: company key absent → company is None."""
    raw = {**JOOBLE_FULL}
    raw.pop("company", None)

    job = normalize_jooble(raw)

    assert job.company is None
