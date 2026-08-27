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

    assert result["fetched"] == 2
    assert result["new"] == 2
    assert result["scored"] == 2
    assert "fetched_by_source" in result
    assert "window_days" in result
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

    assert result["fetched"] == 0
    assert result["new"] == 0
    assert result["scored"] == 0
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


# ---------------------------------------------------------------------------
# GET /jobs endpoint tests
# ---------------------------------------------------------------------------

# Helpers ----------------------------------------------------------------

def _job_row(
    id: str = "aaaa0000-0000-0000-0000-000000000001",
    source: str = "adzuna",
    title: str = "Software Engineer",
    company: str = "Acme Corp",
    location: str = "Toronto, ON",
    salary_min: int = 90_000,
    salary_max: int = 120_000,
    url: str = "https://example.com/1",
    date_fetched: str = "2026-08-26T14:00:00+00:00",
    raw_score: float = 72.0,
    llm_score: float | None = None,
    llm_rationale: str | None = None,
) -> dict:
    return {
        "id": id,
        "source": source,
        "title": title,
        "company": company,
        "location": location,
        "salary_min": salary_min,
        "salary_max": salary_max,
        "url": url,
        "date_fetched": date_fetched,
        "raw_score": raw_score,
        "llm_score": llm_score,
        "llm_rationale": llm_rationale,
        "description": "Build great things.",
        "external_id": id,
    }


def _status_row(
    job_id: str,
    status: str = "New",
    notes: str = "",
) -> dict:
    return {
        "id": f"ssss-{job_id}",
        "job_id": job_id,
        "status": status,
        "notes": notes,
        "history": [],
        "updated_at": "2026-08-26T14:00:00+00:00",
    }


def _make_jobs_mock_db(job_rows: list[dict], status_rows: list[dict] | None = None) -> MagicMock:
    """Mock Supabase client that returns job rows then status rows.

    Supports chained calls:
      db.table("job").select("*").gte(...).eq(...).execute()
      db.table("application_status").select("*").in_(...).execute()
    """
    status_rows = status_rows or []

    job_execute = MagicMock()
    job_execute.data = job_rows

    status_execute = MagicMock()
    status_execute.data = status_rows

    job_chain = MagicMock()
    job_chain.execute.return_value = job_execute
    job_chain.select.return_value = job_chain
    job_chain.gte.return_value = job_chain
    job_chain.eq.return_value = job_chain
    job_chain.in_.return_value = job_chain

    status_chain = MagicMock()
    status_chain.execute.return_value = status_execute
    status_chain.select.return_value = status_chain
    status_chain.in_.return_value = status_chain

    mock_db = MagicMock()

    def _table_dispatch(name: str) -> MagicMock:
        if name == "application_status":
            return status_chain
        return job_chain

    mock_db.table.side_effect = _table_dispatch
    return mock_db


# Tests ------------------------------------------------------------------


def test_get_jobs_returns_200_with_correct_shape():
    """GET /jobs returns 200 with total and jobs list."""
    job = _job_row()
    mock_db = _make_jobs_mock_db([job])
    app.dependency_overrides[get_db] = lambda: mock_db

    client = TestClient(app)
    response = client.get("/jobs/")

    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "jobs" in data
    assert data["total"] == 1
    assert len(data["jobs"]) == 1


def test_get_jobs_correct_field_shape():
    """Response job objects include all required fields."""
    job = _job_row(llm_score=85.0, llm_rationale="Great match.")
    mock_db = _make_jobs_mock_db([job], [_status_row(job["id"], "Saved", "follow up")])
    app.dependency_overrides[get_db] = lambda: mock_db

    client = TestClient(app)
    response = client.get("/jobs/")

    j = response.json()["jobs"][0]
    assert j["id"] == job["id"]
    assert j["source"] == "adzuna"
    assert j["title"] == "Software Engineer"
    assert j["company"] == "Acme Corp"
    assert j["llm_score"] == 85.0
    assert j["llm_rationale"] == "Great match."
    assert j["status"] == "Saved"
    assert j["notes"] == "follow up"


def test_get_jobs_ordered_by_raw_score_desc():
    """Jobs are returned in raw_score descending order."""
    job_low = _job_row(id="aaaa0000-0000-0000-0000-000000000001", raw_score=40.0)
    job_high = _job_row(id="bbbb0000-0000-0000-0000-000000000002", raw_score=90.0)
    job_mid = _job_row(id="cccc0000-0000-0000-0000-000000000003", raw_score=65.0)

    mock_db = _make_jobs_mock_db([job_low, job_high, job_mid])
    app.dependency_overrides[get_db] = lambda: mock_db

    client = TestClient(app)
    response = client.get("/jobs/")

    scores = [j["raw_score"] for j in response.json()["jobs"]]
    assert scores == [90.0, 65.0, 40.0]


def test_get_jobs_deterministic_secondary_sort_by_id():
    """Jobs with equal raw_score are sorted by id ascending."""
    job_b = _job_row(id="bbbb0000-0000-0000-0000-000000000002", raw_score=75.0)
    job_a = _job_row(id="aaaa0000-0000-0000-0000-000000000001", raw_score=75.0)
    job_c = _job_row(id="cccc0000-0000-0000-0000-000000000003", raw_score=75.0)

    mock_db = _make_jobs_mock_db([job_b, job_a, job_c])
    app.dependency_overrides[get_db] = lambda: mock_db

    client = TestClient(app)
    response = client.get("/jobs/")

    ids = [j["id"] for j in response.json()["jobs"]]
    assert ids == [
        "aaaa0000-0000-0000-0000-000000000001",
        "bbbb0000-0000-0000-0000-000000000002",
        "cccc0000-0000-0000-0000-000000000003",
    ]


def test_get_jobs_filter_min_score():
    """min_score filters out jobs below the threshold."""
    job_high = _job_row(id="bbbb0000-0000-0000-0000-000000000002", raw_score=80.0)

    # DB-level filter is applied via gte; we simulate by only returning matching rows
    mock_db = _make_jobs_mock_db([job_high])
    app.dependency_overrides[get_db] = lambda: mock_db

    client = TestClient(app)
    response = client.get("/jobs/?min_score=50")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    # Verify the gte filter was applied with the correct value
    job_chain = mock_db.table("job")
    job_chain.gte.assert_called_once_with("raw_score", 50)


def test_get_jobs_filter_source():
    """source filter is passed to the DB query."""
    job = _job_row(source="jooble")
    mock_db = _make_jobs_mock_db([job])
    app.dependency_overrides[get_db] = lambda: mock_db

    client = TestClient(app)
    response = client.get("/jobs/?source=jooble")

    assert response.status_code == 200
    job_chain = mock_db.table("job")
    job_chain.eq.assert_called_once_with("source", "jooble")


def test_get_jobs_invalid_source_returns_422():
    """Passing an invalid source value returns 422."""
    mock_db = _make_jobs_mock_db([])
    app.dependency_overrides[get_db] = lambda: mock_db

    client = TestClient(app)
    response = client.get("/jobs/?source=linkedin")

    assert response.status_code == 422


def test_get_jobs_filter_since():
    """since filter is passed to the DB query as ISO date."""
    job = _job_row(date_fetched="2026-08-27T10:00:00+00:00")
    mock_db = _make_jobs_mock_db([job])
    app.dependency_overrides[get_db] = lambda: mock_db

    client = TestClient(app)
    response = client.get("/jobs/?since=2026-08-27")

    assert response.status_code == 200
    job_chain = mock_db.table("job")
    job_chain.gte.assert_any_call("date_fetched", "2026-08-27")


def test_get_jobs_filter_status_saved():
    """status filter returns only jobs with that application status."""
    job_new = _job_row(id="aaaa0000-0000-0000-0000-000000000001")
    job_saved = _job_row(id="bbbb0000-0000-0000-0000-000000000002")

    mock_db = _make_jobs_mock_db(
        [job_new, job_saved],
        [_status_row(job_saved["id"], "Saved")],
    )
    app.dependency_overrides[get_db] = lambda: mock_db

    client = TestClient(app)
    response = client.get("/jobs/?status=Saved")

    data = response.json()
    assert data["total"] == 1
    assert data["jobs"][0]["id"] == job_saved["id"]
    assert data["jobs"][0]["status"] == "Saved"


def test_get_jobs_filter_status_new_includes_no_row_jobs():
    """status=New matches both explicit 'New' rows and jobs with no application_status row."""
    job_no_row = _job_row(id="aaaa0000-0000-0000-0000-000000000001", raw_score=80.0)
    job_explicit_new = _job_row(id="bbbb0000-0000-0000-0000-000000000002", raw_score=70.0)
    job_saved = _job_row(id="cccc0000-0000-0000-0000-000000000003", raw_score=60.0)

    mock_db = _make_jobs_mock_db(
        [job_no_row, job_explicit_new, job_saved],
        [
            _status_row(job_explicit_new["id"], "New"),
            _status_row(job_saved["id"], "Saved"),
        ],
    )
    app.dependency_overrides[get_db] = lambda: mock_db

    client = TestClient(app)
    response = client.get("/jobs/?status=New")

    data = response.json()
    assert data["total"] == 2
    returned_ids = {j["id"] for j in data["jobs"]}
    assert returned_ids == {job_no_row["id"], job_explicit_new["id"]}


def test_get_jobs_default_status_and_notes_when_no_app_status_row():
    """Jobs with no application_status row get status='New' and notes=''."""
    job = _job_row()
    mock_db = _make_jobs_mock_db([job], status_rows=[])
    app.dependency_overrides[get_db] = lambda: mock_db

    client = TestClient(app)
    response = client.get("/jobs/")

    j = response.json()["jobs"][0]
    assert j["status"] == "New"
    assert j["notes"] == ""


def test_get_jobs_null_llm_fields():
    """Jobs not yet re-ranked have null llm_score and llm_rationale."""
    job = _job_row(llm_score=None, llm_rationale=None)
    mock_db = _make_jobs_mock_db([job])
    app.dependency_overrides[get_db] = lambda: mock_db

    client = TestClient(app)
    response = client.get("/jobs/")

    j = response.json()["jobs"][0]
    assert j["llm_score"] is None
    assert j["llm_rationale"] is None


def test_get_jobs_empty_result():
    """When no jobs match, returns 200 with total=0 and empty list."""
    mock_db = _make_jobs_mock_db([])
    app.dependency_overrides[get_db] = lambda: mock_db

    client = TestClient(app)
    response = client.get("/jobs/")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["jobs"] == []


def test_get_jobs_pagination_total_unaffected():
    """total reflects all filtered results regardless of limit/offset."""
    jobs = [
        _job_row(id=f"aaaa0000-0000-0000-0000-{i:012d}", raw_score=float(100 - i))
        for i in range(10)
    ]
    mock_db = _make_jobs_mock_db(jobs)
    app.dependency_overrides[get_db] = lambda: mock_db

    client = TestClient(app)
    response = client.get("/jobs/?limit=3&offset=0")

    data = response.json()
    assert data["total"] == 10
    assert len(data["jobs"]) == 3


def test_get_jobs_pagination_offset():
    """offset skips the appropriate number of results."""
    jobs = [
        _job_row(id=f"aaaa0000-0000-0000-0000-{i:012d}", raw_score=float(100 - i))
        for i in range(5)
    ]
    mock_db = _make_jobs_mock_db(jobs)
    app.dependency_overrides[get_db] = lambda: mock_db

    client = TestClient(app)
    response = client.get("/jobs/?limit=2&offset=2")

    data = response.json()
    assert data["total"] == 5
    assert len(data["jobs"]) == 2
    # After sorting by raw_score desc, offset=2 skips the first 2
    assert data["jobs"][0]["raw_score"] == 98.0


def test_get_jobs_offset_past_end_returns_empty_not_error():
    """Requesting an offset beyond the total returns empty jobs list, not an error."""
    job = _job_row()
    mock_db = _make_jobs_mock_db([job])
    app.dependency_overrides[get_db] = lambda: mock_db

    client = TestClient(app)
    response = client.get("/jobs/?offset=999")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["jobs"] == []


def test_get_jobs_combined_filters():
    """Multiple filters can be combined: source + min_score + status."""
    job_match = _job_row(
        id="aaaa0000-0000-0000-0000-000000000001",
        source="adzuna",
        raw_score=85.0,
    )
    # DB already filtered by source/min_score — only job_match returned
    mock_db = _make_jobs_mock_db(
        [job_match],
        [_status_row(job_match["id"], "Saved")],
    )
    app.dependency_overrides[get_db] = lambda: mock_db

    client = TestClient(app)
    response = client.get("/jobs/?source=adzuna&min_score=80&status=Saved")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["jobs"][0]["status"] == "Saved"
