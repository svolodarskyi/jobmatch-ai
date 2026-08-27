"""Tests for GET /fetch-runs endpoint.

All collaborators are mocked — no live network or database connections.
"""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_RUN = {
    "id": "00000000-0000-0000-0000-000000000001",
    "started_at": "2026-08-27T09:00:00Z",
    "completed_at": "2026-08-27T09:00:08Z",
    "window_days": 1,
    "fetched_total": 97,
    "new_jobs": 23,
    "updated_jobs": 4,
    "scored_pass1": 97,
    "scored_pass2": 20,
    "source_stats": {"adzuna": {"retrieved": 40, "new": 12, "updated": 2}},
    "tokens_in": 7841,
    "tokens_out": 591,
    "cost_usd": 0.001531,
    "status": "ok",
    "error_message": None,
}


def _make_mock_db(rows: list[dict]) -> MagicMock:
    """Return a MagicMock mimicking supabase.Client chained calls.

    Supports: .table().select("*").order(...).limit(...).execute()
    """
    execute_result = MagicMock()
    execute_result.data = rows

    chain = MagicMock()
    chain.execute.return_value = execute_result
    chain.select.return_value = chain
    chain.order.return_value = chain
    chain.limit.return_value = chain

    mock_db = MagicMock()
    mock_db.table.return_value = chain
    return mock_db


@pytest.fixture(autouse=True)
def _reset_overrides():
    """Ensure dependency overrides are cleaned up after every test."""
    yield
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_list_fetch_runs_returns_runs():
    """GET /fetch-runs returns 200 with one run matching SAMPLE_RUN."""
    mock_db = _make_mock_db([SAMPLE_RUN])
    app.dependency_overrides[get_db] = lambda: mock_db

    client = TestClient(app)
    response = client.get("/fetch-runs")

    assert response.status_code == 200
    data = response.json()
    assert "runs" in data
    assert len(data["runs"]) == 1
    run = data["runs"][0]
    assert run["id"] == SAMPLE_RUN["id"]
    assert run["status"] == "ok"
    assert run["source_stats"] == SAMPLE_RUN["source_stats"]


def test_list_fetch_runs_empty_table():
    """GET /fetch-runs returns 200 with runs=[] when table is empty."""
    mock_db = _make_mock_db([])
    app.dependency_overrides[get_db] = lambda: mock_db

    client = TestClient(app)
    response = client.get("/fetch-runs")

    assert response.status_code == 200
    data = response.json()
    assert data["runs"] == []


def test_list_fetch_runs_limit_param():
    """GET /fetch-runs?limit=5 passes limit=5 to the DB chain."""
    mock_db = _make_mock_db([])
    app.dependency_overrides[get_db] = lambda: mock_db

    client = TestClient(app)
    response = client.get("/fetch-runs?limit=5")

    assert response.status_code == 200
    chain = mock_db.table.return_value
    chain.limit.assert_called_once_with(5)
