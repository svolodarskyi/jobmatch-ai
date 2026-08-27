"""Tests for POST /jobs/fetch endpoint and pipeline.run() orchestration.

All collaborators are mocked — no live network or database connections.

Async pipeline tests use ``asyncio.run()`` directly (no pytest-asyncio needed).
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.db import get_db
from app.main import app
from app.models import Profile
from app.scoring.pass2 import RankedJob
from app.sources.normalize import Job

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

FIXED_PROFILE_ROW = {
    "id": "00000000-0000-0000-0000-000000000001",
    "target_titles": ["Software Engineer"],
    "skills": ["Python", "FastAPI"],
    "seniority": "mid",
    "locations": ["Toronto"],
    "salary_min": 80000,
    "salary_max": 120000,
    "preferences": {},
}

SAMPLE_PROFILE = Profile(
    target_titles=["Software Engineer"],
    skills=["Python", "FastAPI"],
    seniority="mid",
    locations=["Toronto"],
    salary_min=80000,
    salary_max=120000,
)


def _make_job(source: str = "adzuna", external_id: str = "abc123") -> Job:
    return Job(
        source=source,
        external_id=external_id,
        title="Software Engineer",
        company="Acme Corp",
        location="Toronto, ON",
        salary_min=90000,
        salary_max=120000,
        description="Build great things with Python.",
        url="https://example.com/jobs/abc123",
    )


def _make_ranked_job(job: Job, llm_score: float | None = 85.0) -> RankedJob:
    return RankedJob(
        job=job,
        pass1_score=72.0,
        llm_score=llm_score,
        llm_rationale="Good Python skills match." if llm_score is not None else None,
    )


def _make_mock_db(profile_rows: list[dict] | None = None) -> MagicMock:
    """Return a MagicMock mimicking supabase.Client chained calls.

    Supports:
      db.table(...).select("*").execute()
      db.table(...).upsert(..., on_conflict=...).execute()
      db.table(...).update(...).eq(...).eq(...).execute()
    """
    profile_rows = profile_rows if profile_rows is not None else [FIXED_PROFILE_ROW]

    execute_result = MagicMock()
    execute_result.data = profile_rows

    chain = MagicMock()
    chain.execute.return_value = execute_result
    chain.select.return_value = chain
    chain.upsert.return_value = chain
    chain.update.return_value = chain
    chain.eq.return_value = chain

    mock_db = MagicMock()
    mock_db.table.return_value = chain
    return mock_db


@pytest.fixture(autouse=True)
def _reset_overrides():
    """Ensure dependency overrides are cleaned up after every test."""
    yield
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# pipeline.run() unit tests — all collaborators mocked
# Uses asyncio.run() so no pytest-asyncio plugin is needed.
# ---------------------------------------------------------------------------


def test_pipeline_run_happy_path_returns_correct_counts():
    """pipeline.run() returns fetched/new/scored counts from mocked collaborators."""
    job_a = _make_job("adzuna", "a1")
    job_j = _make_job("jooble", "j1")
    ranked = [_make_ranked_job(job_a), _make_ranked_job(job_j)]

    mock_db = _make_mock_db()

    with (
        patch("app.pipeline.adzuna.fetch_jobs", new=AsyncMock(return_value=[{"id": "a1"}])),
        patch("app.pipeline.jooble.fetch_jobs", new=AsyncMock(return_value=[{"id": "j1"}])),
        patch("app.pipeline.normalize_adzuna", return_value=job_a),
        patch("app.pipeline.normalize_jooble", return_value=job_j),
        patch("app.pipeline.persist_jobs", return_value=2) as mock_persist,
        patch("app.pipeline.pass1.score", return_value={"score": 72.0}),
        patch("app.pipeline.pass2.rerank", return_value=ranked) as mock_rerank,
    ):
        from app.pipeline import run

        result = asyncio.run(run(SAMPLE_PROFILE, mock_db))

    assert result == {"fetched": 2, "new": 2, "scored": 2}
    mock_persist.assert_called_once()
    mock_rerank.assert_called_once()


def test_pipeline_run_pass2_failure_still_returns_summary():
    """When Pass 2 returns jobs with llm_score=None, pipeline completes normally."""
    job_a = _make_job("adzuna", "a1")
    # Simulate all Pass 2 calls failing — llm_score/rationale are None
    ranked = [_make_ranked_job(job_a, llm_score=None)]

    mock_db = _make_mock_db()

    with (
        patch("app.pipeline.adzuna.fetch_jobs", new=AsyncMock(return_value=[{"id": "a1"}])),
        patch("app.pipeline.jooble.fetch_jobs", new=AsyncMock(return_value=[])),
        patch("app.pipeline.normalize_adzuna", return_value=job_a),
        patch("app.pipeline.persist_jobs", return_value=1),
        patch("app.pipeline.pass1.score", return_value={"score": 60.0}),
        patch("app.pipeline.pass2.rerank", return_value=ranked),
    ):
        from app.pipeline import run

        result = asyncio.run(run(SAMPLE_PROFILE, mock_db))

    # scored reflects actual re-ranked count even when llm_score is None
    assert result["scored"] == 1
    assert result["fetched"] == 1
    assert result["new"] == 1
    # No update call to DB because llm_score is None
    chain = mock_db.table.return_value
    chain.update.assert_not_called()


def test_pipeline_run_dedup_does_not_inflate_new():
    """'new' count comes from persist_jobs — dedup (returning lower count) is reflected."""
    job_a = _make_job("adzuna", "dupe-1")
    ranked = [_make_ranked_job(job_a)]

    mock_db = _make_mock_db()

    with (
        patch(
            "app.pipeline.adzuna.fetch_jobs",
            new=AsyncMock(return_value=[{"id": "dupe-1"}, {"id": "dupe-1"}]),
        ),
        patch("app.pipeline.jooble.fetch_jobs", new=AsyncMock(return_value=[])),
        patch("app.pipeline.normalize_adzuna", return_value=job_a),
        # persist_jobs returns 1 even though 2 raw items were fetched (dedup scenario)
        patch("app.pipeline.persist_jobs", return_value=1) as mock_persist,
        patch("app.pipeline.pass1.score", return_value={"score": 70.0}),
        patch("app.pipeline.pass2.rerank", return_value=ranked),
    ):
        from app.pipeline import run

        result = asyncio.run(run(SAMPLE_PROFILE, mock_db))

    assert result["fetched"] == 2  # 2 raw listings retrieved
    assert result["new"] == 1  # only 1 row upserted (dedup)
    mock_persist.assert_called_once()


def test_pipeline_run_pass2_cap_is_respected():
    """pipeline.run() passes cap=20 to pass2.rerank."""
    job = _make_job()
    ranked = [_make_ranked_job(job)]

    mock_db = _make_mock_db()

    with (
        patch("app.pipeline.adzuna.fetch_jobs", new=AsyncMock(return_value=[{"id": "a1"}])),
        patch("app.pipeline.jooble.fetch_jobs", new=AsyncMock(return_value=[])),
        patch("app.pipeline.normalize_adzuna", return_value=job),
        patch("app.pipeline.persist_jobs", return_value=1),
        patch("app.pipeline.pass1.score", return_value={"score": 80.0}),
        patch("app.pipeline.pass2.rerank", return_value=ranked) as mock_rerank,
    ):
        from app.pipeline import run

        asyncio.run(run(SAMPLE_PROFILE, mock_db))

    # Verify rerank was called with cap=20
    _, kwargs = mock_rerank.call_args
    assert kwargs.get("cap") == 20


def test_pipeline_run_persists_llm_scores_to_db():
    """pipeline.run() updates llm_score and llm_rationale in the DB for ranked jobs."""
    job_a = _make_job("adzuna", "a1")
    ranked = [_make_ranked_job(job_a, llm_score=90.0)]

    mock_db = _make_mock_db()

    with (
        patch("app.pipeline.adzuna.fetch_jobs", new=AsyncMock(return_value=[{"id": "a1"}])),
        patch("app.pipeline.jooble.fetch_jobs", new=AsyncMock(return_value=[])),
        patch("app.pipeline.normalize_adzuna", return_value=job_a),
        patch("app.pipeline.persist_jobs", return_value=1),
        patch("app.pipeline.pass1.score", return_value={"score": 72.0}),
        patch("app.pipeline.pass2.rerank", return_value=ranked),
    ):
        from app.pipeline import run

        asyncio.run(run(SAMPLE_PROFILE, mock_db))

    chain = mock_db.table.return_value
    chain.update.assert_called_once_with(
        {"llm_score": 90.0, "llm_rationale": "Good Python skills match."}
    )


def test_pipeline_run_empty_titles_returns_zero_counts():
    """When the profile has no target_titles, pipeline returns zeros without calling sources."""
    profile_no_titles = Profile(
        target_titles=[],
        skills=["Python"],
        seniority="mid",
        locations=["Toronto"],
    )
    mock_db = _make_mock_db()

    with (
        patch("app.pipeline.adzuna.fetch_jobs", new=AsyncMock()) as mock_adzuna,
        patch("app.pipeline.jooble.fetch_jobs", new=AsyncMock()) as mock_jooble,
        patch("app.pipeline.persist_jobs", return_value=0),
        patch("app.pipeline.pass2.rerank", return_value=[]),
    ):
        from app.pipeline import run

        result = asyncio.run(run(profile_no_titles, mock_db))

    assert result == {"fetched": 0, "new": 0, "scored": 0}
    mock_adzuna.assert_not_called()
    mock_jooble.assert_not_called()


# ---------------------------------------------------------------------------
# POST /jobs/fetch endpoint tests — TestClient + dependency_overrides
# ---------------------------------------------------------------------------


def test_post_fetch_happy_path():
    """POST /jobs/fetch returns 200 with fetched/new/scored summary."""
    mock_db = _make_mock_db([FIXED_PROFILE_ROW])
    app.dependency_overrides[get_db] = lambda: mock_db

    job_a = _make_job("adzuna", "a1")
    ranked = [_make_ranked_job(job_a)]

    with (
        patch("app.pipeline.adzuna.fetch_jobs", new=AsyncMock(return_value=[{"id": "a1"}])),
        patch("app.pipeline.jooble.fetch_jobs", new=AsyncMock(return_value=[])),
        patch("app.pipeline.normalize_adzuna", return_value=job_a),
        patch("app.pipeline.persist_jobs", return_value=1),
        patch("app.pipeline.pass1.score", return_value={"score": 72.0}),
        patch("app.pipeline.pass2.rerank", return_value=ranked),
    ):
        client = TestClient(app)
        response = client.post("/jobs/fetch")

    assert response.status_code == 200
    data = response.json()
    assert data["fetched"] == 1
    assert data["new"] == 1
    assert data["scored"] == 1


def test_post_fetch_no_profile_returns_404():
    """POST /jobs/fetch returns 404 when no profile has been saved."""
    mock_db = _make_mock_db([])  # Empty profile table
    app.dependency_overrides[get_db] = lambda: mock_db

    client = TestClient(app)
    response = client.post("/jobs/fetch")

    assert response.status_code == 404
    assert "profile" in response.json()["detail"].lower()


def test_post_fetch_pass2_failure_still_returns_200():
    """POST /jobs/fetch returns 200 even when all Pass 2 LLM scores are None."""
    mock_db = _make_mock_db([FIXED_PROFILE_ROW])
    app.dependency_overrides[get_db] = lambda: mock_db

    job_a = _make_job("adzuna", "a1")
    # All pass2 results have llm_score=None (failure fallback)
    ranked = [_make_ranked_job(job_a, llm_score=None)]

    with (
        patch("app.pipeline.adzuna.fetch_jobs", new=AsyncMock(return_value=[{"id": "a1"}])),
        patch("app.pipeline.jooble.fetch_jobs", new=AsyncMock(return_value=[])),
        patch("app.pipeline.normalize_adzuna", return_value=job_a),
        patch("app.pipeline.persist_jobs", return_value=1),
        patch("app.pipeline.pass1.score", return_value={"score": 60.0}),
        patch("app.pipeline.pass2.rerank", return_value=ranked),
    ):
        client = TestClient(app)
        response = client.post("/jobs/fetch")

    assert response.status_code == 200
    data = response.json()
    assert data["scored"] == 1
