"""Tests for PATCH /jobs/{id}/status, PATCH /jobs/{id}/notes, and
PATCH /jobs/{id}/fits_me endpoints.

All collaborators are mocked — no live network or database connections.

Ten concrete test cases:
  1. PATCH /jobs/{id}/status happy path: creates initial history entry
  2. PATCH /jobs/{id}/status with existing history: appends to history
  3. PATCH /jobs/{id}/status with invalid status value: returns 422
  4. PATCH /jobs/{id}/status with unknown job_id: returns 404
  5. PATCH /jobs/{id}/notes happy path: returns correct shape
  6. PATCH /jobs/{id}/notes with unknown job_id: returns 404
  7. PATCH /jobs/{id}/fits_me sets it to true
  8. PATCH /jobs/{id}/fits_me sets it back to false
  9. PATCH /jobs/{id}/fits_me with unknown job_id: returns 404
  10. PATCH /jobs/{id}/fits_me with invalid body: returns 422
"""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

KNOWN_JOB_ID = "aaaa0000-0000-0000-0000-000000000001"
UNKNOWN_JOB_ID = "ffff0000-0000-0000-0000-000000000099"

JOB_ROW = {
    "id": KNOWN_JOB_ID,
    "source": "adzuna",
    "external_id": "abc123",
    "title": "Software Engineer",
    "company": "Acme Corp",
    "location": "Toronto, ON",
    "salary_min": 90000,
    "salary_max": 120000,
    "description": "Build great things.",
    "url": "https://example.com/jobs/abc123",
    "date_fetched": "2026-08-26T10:00:00+00:00",
    "raw_score": 72.0,
    "llm_score": None,
    "llm_rationale": None,
}

EXISTING_HISTORY = [
    {"status": "New", "changed_at": "2026-08-24T09:00:00+00:00"},
]

EXISTING_STATUS_ROW = {
    "id": "ssss-0001",
    "job_id": KNOWN_JOB_ID,
    "status": "New",
    "notes": "",
    "history": EXISTING_HISTORY,
    "updated_at": "2026-08-24T09:00:00+00:00",
}


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------


def _make_status_mock_db(
    job_rows: list[dict],
    status_rows: list[dict] | None = None,
) -> MagicMock:
    """Return a MagicMock mimicking supabase.Client for status router tests.

    Dispatches table calls:
      - "job"                → returns job_rows
      - "application_status" → returns status_rows

    Supports chained calls:
      db.table(...).select("*").eq("id", ...).execute()
      db.table(...).select("*").eq("job_id", ...).execute()
      db.table(...).upsert(..., on_conflict=...).execute()
    """
    status_rows = status_rows if status_rows is not None else []

    job_execute = MagicMock()
    job_execute.data = job_rows

    status_execute = MagicMock()
    status_execute.data = status_rows

    upsert_execute = MagicMock()
    upsert_execute.data = []

    job_chain = MagicMock()
    job_chain.execute.return_value = job_execute
    job_chain.select.return_value = job_chain
    job_chain.eq.return_value = job_chain
    job_chain.update.return_value = job_chain

    status_chain = MagicMock()
    # select returns a chain that yields status_rows on execute
    status_select_chain = MagicMock()
    status_select_chain.execute.return_value = status_execute
    status_select_chain.eq.return_value = status_select_chain

    # upsert returns a chain that executes without error
    status_upsert_chain = MagicMock()
    status_upsert_chain.execute.return_value = upsert_execute

    status_chain.select.return_value = status_select_chain
    status_chain.upsert.return_value = status_upsert_chain

    mock_db = MagicMock()

    def _table_dispatch(name: str) -> MagicMock:
        if name == "application_status":
            return status_chain
        return job_chain  # "job" table

    mock_db.table.side_effect = _table_dispatch
    return mock_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_overrides() -> None:  # type: ignore[return]
    """Ensure dependency overrides are cleaned up after every test."""
    yield  # type: ignore[misc]
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


def test_patch_status_happy_path_creates_initial_history():
    """PATCH /jobs/{id}/status creates the first history entry on a job with no
    existing application_status row."""
    mock_db = _make_status_mock_db(job_rows=[JOB_ROW], status_rows=[])
    app.dependency_overrides[get_db] = lambda: mock_db

    client = TestClient(app)
    response = client.patch(f"/jobs/{KNOWN_JOB_ID}/status", json={"status": "Applied"})

    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == KNOWN_JOB_ID
    assert data["status"] == "Applied"
    assert isinstance(data["history"], list)
    assert len(data["history"]) == 1
    assert data["history"][0]["status"] == "Applied"
    assert "changed_at" in data["history"][0]
    assert "updated_at" in data


def test_patch_status_appends_to_existing_history():
    """PATCH /jobs/{id}/status appends a new entry when history already exists;
    it does not overwrite."""
    mock_db = _make_status_mock_db(job_rows=[JOB_ROW], status_rows=[EXISTING_STATUS_ROW])
    app.dependency_overrides[get_db] = lambda: mock_db

    client = TestClient(app)
    response = client.patch(f"/jobs/{KNOWN_JOB_ID}/status", json={"status": "Interviewing"})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "Interviewing"
    # Should have the original "New" entry + the new "Interviewing" entry
    assert len(data["history"]) == 2
    assert data["history"][0]["status"] == "New"
    assert data["history"][1]["status"] == "Interviewing"


def test_patch_status_invalid_value_returns_422():
    """PATCH /jobs/{id}/status with a status not in the allowed enum returns 422."""
    mock_db = _make_status_mock_db(job_rows=[JOB_ROW])
    app.dependency_overrides[get_db] = lambda: mock_db

    client = TestClient(app)
    response = client.patch(f"/jobs/{KNOWN_JOB_ID}/status", json={"status": "Ghosted"})

    assert response.status_code == 422


def test_patch_status_unknown_job_id_returns_404():
    """PATCH /jobs/{id}/status returns 404 when the job_id does not exist in
    the job table; no application_status row should be created."""
    # job table returns empty — job not found
    mock_db = _make_status_mock_db(job_rows=[], status_rows=[])
    app.dependency_overrides[get_db] = lambda: mock_db

    client = TestClient(app)
    response = client.patch(f"/jobs/{UNKNOWN_JOB_ID}/status", json={"status": "Applied"})

    assert response.status_code == 404
    # Verify no upsert was attempted on application_status
    status_chain = mock_db.table("application_status")
    status_chain.upsert.assert_not_called()


def test_patch_notes_happy_path():
    """PATCH /jobs/{id}/notes returns 200 with job_id, notes, and updated_at;
    it does not modify status or history."""
    mock_db = _make_status_mock_db(job_rows=[JOB_ROW], status_rows=[EXISTING_STATUS_ROW])
    app.dependency_overrides[get_db] = lambda: mock_db

    client = TestClient(app)
    response = client.patch(
        f"/jobs/{KNOWN_JOB_ID}/notes",
        json={"notes": "Recruiter is Jane Smith."},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == KNOWN_JOB_ID
    assert data["notes"] == "Recruiter is Jane Smith."
    assert "updated_at" in data
    # Response must not include status or history fields
    assert "status" not in data
    assert "history" not in data


def test_patch_notes_unknown_job_id_returns_404():
    """PATCH /jobs/{id}/notes returns 404 when the job_id does not exist in
    the job table; no application_status row should be created."""
    # job table returns empty — job not found
    mock_db = _make_status_mock_db(job_rows=[], status_rows=[])
    app.dependency_overrides[get_db] = lambda: mock_db

    client = TestClient(app)
    response = client.patch(
        f"/jobs/{UNKNOWN_JOB_ID}/notes",
        json={"notes": "Some note."},
    )

    assert response.status_code == 404
    # Verify no upsert was attempted on application_status
    status_chain = mock_db.table("application_status")
    status_chain.upsert.assert_not_called()


def test_patch_fits_me_sets_true():
    """PATCH /jobs/{id}/fits_me with {"fits_me": true} returns 200 and updates
    the job table directly (not application_status)."""
    mock_db = _make_status_mock_db(job_rows=[JOB_ROW], status_rows=[])
    app.dependency_overrides[get_db] = lambda: mock_db

    client = TestClient(app)
    response = client.patch(f"/jobs/{KNOWN_JOB_ID}/fits_me", json={"fits_me": True})

    assert response.status_code == 200
    assert response.json() == {"job_id": KNOWN_JOB_ID, "fits_me": True}

    job_chain = mock_db.table("job")
    job_chain.update.assert_called_once_with({"fits_me": True})
    # Never touches application_status for this endpoint
    status_chain = mock_db.table("application_status")
    status_chain.upsert.assert_not_called()


def test_patch_fits_me_sets_false():
    """PATCH /jobs/{id}/fits_me with {"fits_me": false} returns 200 and can
    flip a previously-set flag back off."""
    mock_db = _make_status_mock_db(job_rows=[JOB_ROW], status_rows=[])
    app.dependency_overrides[get_db] = lambda: mock_db

    client = TestClient(app)
    response = client.patch(f"/jobs/{KNOWN_JOB_ID}/fits_me", json={"fits_me": False})

    assert response.status_code == 200
    assert response.json() == {"job_id": KNOWN_JOB_ID, "fits_me": False}

    job_chain = mock_db.table("job")
    job_chain.update.assert_called_once_with({"fits_me": False})


def test_patch_fits_me_unknown_job_id_returns_404():
    """PATCH /jobs/{id}/fits_me returns 404 when the job_id does not exist in
    the job table; no update should be attempted."""
    mock_db = _make_status_mock_db(job_rows=[], status_rows=[])
    app.dependency_overrides[get_db] = lambda: mock_db

    client = TestClient(app)
    response = client.patch(f"/jobs/{UNKNOWN_JOB_ID}/fits_me", json={"fits_me": True})

    assert response.status_code == 404
    job_chain = mock_db.table("job")
    job_chain.update.assert_not_called()


def test_patch_fits_me_invalid_body_returns_422():
    """PATCH /jobs/{id}/fits_me with a missing or non-boolean fits_me value
    returns 422 rather than 500 or a silent coercion."""
    mock_db = _make_status_mock_db(job_rows=[JOB_ROW], status_rows=[])
    app.dependency_overrides[get_db] = lambda: mock_db

    client = TestClient(app)

    missing_body_response = client.patch(f"/jobs/{KNOWN_JOB_ID}/fits_me", json={})
    assert missing_body_response.status_code == 422

    # Pydantic v2 coerces some strings ("true"/"yes"/"1"...) to bool, so use a
    # value with no valid bool coercion to exercise the non-boolean branch.
    non_bool_response = client.patch(
        f"/jobs/{KNOWN_JOB_ID}/fits_me", json={"fits_me": "banana"}
    )
    assert non_bool_response.status_code == 422
