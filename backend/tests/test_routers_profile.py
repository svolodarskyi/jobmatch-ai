"""Tests for GET /profile and PUT /profile endpoints.

All Supabase DB calls are mocked via FastAPI dependency_overrides so no real
network or Supabase connection is required.
"""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app

FIXED_ID = "00000000-0000-0000-0000-000000000001"

SAMPLE_PROFILE = {
    "id": FIXED_ID,
    "target_titles": ["Software Engineer", "Backend Developer"],
    "skills": ["Python", "FastAPI"],
    "seniority": "mid",
    "locations": ["Toronto", "Remote"],
    "salary_min": 80000,
    "salary_max": 120000,
    "preferences": {"open_to_relocation": False},
}


def _make_mock_db(rows: list[dict]) -> MagicMock:
    """Return a MagicMock that mimics supabase.Client chained calls.

    Supports: db.table(...).select("*").execute()
              db.table(...).upsert({...}).execute()
    """
    execute_result = MagicMock()
    execute_result.data = rows

    chain = MagicMock()
    chain.execute.return_value = execute_result
    # select, upsert — all return the same chain so .execute() is reachable
    chain.select.return_value = chain
    chain.upsert.return_value = chain

    mock_db = MagicMock()
    mock_db.table.return_value = chain
    return mock_db


@pytest.fixture(autouse=True)
def _reset_overrides():
    """Ensure dependency overrides are cleaned up after every test."""
    yield
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# GET /profile — 404 when no profile exists
# ---------------------------------------------------------------------------


def test_get_profile_not_found() -> None:
    mock_db = _make_mock_db([])
    app.dependency_overrides[get_db] = lambda: mock_db

    client = TestClient(app)
    response = client.get("/profile")

    assert response.status_code == 404
    assert response.json()["detail"] == "Profile not found"


# ---------------------------------------------------------------------------
# PUT /profile — creates a new profile, returns saved data
# ---------------------------------------------------------------------------


def test_put_profile_creates_profile() -> None:
    # After upsert the select returns the saved row
    mock_db = _make_mock_db([SAMPLE_PROFILE])
    app.dependency_overrides[get_db] = lambda: mock_db

    client = TestClient(app)
    payload = {
        "target_titles": ["Software Engineer", "Backend Developer"],
        "skills": ["Python", "FastAPI"],
        "seniority": "mid",
        "locations": ["Toronto", "Remote"],
        "salary_min": 80000,
        "salary_max": 120000,
        "preferences": {"open_to_relocation": False},
    }
    response = client.put("/profile", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["skills"] == ["Python", "FastAPI"]
    assert data["seniority"] == "mid"
    assert data["salary_min"] == 80000
    assert data["id"] == FIXED_ID


# ---------------------------------------------------------------------------
# GET /profile — 200 when profile exists (mock returns a row)
# ---------------------------------------------------------------------------


def test_get_profile_returns_existing_profile() -> None:
    mock_db = _make_mock_db([SAMPLE_PROFILE])
    app.dependency_overrides[get_db] = lambda: mock_db

    client = TestClient(app)
    response = client.get("/profile")

    assert response.status_code == 200
    data = response.json()
    assert data["target_titles"] == ["Software Engineer", "Backend Developer"]
    assert data["locations"] == ["Toronto", "Remote"]
    assert data["preferences"] == {"open_to_relocation": False}


# ---------------------------------------------------------------------------
# PUT /profile — overwrites an existing profile
# ---------------------------------------------------------------------------


def test_put_profile_overwrites_existing() -> None:
    updated_profile = {
        **SAMPLE_PROFILE,
        "skills": ["Python", "FastAPI", "PostgreSQL"],
        "salary_max": 140000,
    }
    mock_db = _make_mock_db([updated_profile])
    app.dependency_overrides[get_db] = lambda: mock_db

    client = TestClient(app)
    payload = {
        "target_titles": ["Software Engineer", "Backend Developer"],
        "skills": ["Python", "FastAPI", "PostgreSQL"],
        "seniority": "mid",
        "locations": ["Toronto", "Remote"],
        "salary_min": 80000,
        "salary_max": 140000,
        "preferences": {"open_to_relocation": False},
    }
    response = client.put("/profile", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert "PostgreSQL" in data["skills"]
    assert data["salary_max"] == 140000
