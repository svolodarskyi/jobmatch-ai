"""Tests for app.pipeline.persist_jobs.

All Supabase DB calls are mocked — no live network or database connections.
"""

from unittest.mock import MagicMock

from supabase import Client

from app.pipeline import persist_jobs
from app.sources.normalize import Job

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_job(source: str = "adzuna", external_id: str = "abc123") -> Job:
    return Job(
        source=source,
        external_id=external_id,
        title="Software Engineer",
        company="Acme Corp",
        location="Toronto, ON",
        salary_min=90000,
        salary_max=120000,
        description="Build great things.",
        url="https://example.com/jobs/abc123",
    )


def _make_mock_db() -> MagicMock:
    """Return a MagicMock that mimics the Supabase client chained call pattern.

    Supports: db.table(...).upsert(...).execute()
    """
    execute_result = MagicMock()
    execute_result.data = []

    chain = MagicMock()
    chain.execute.return_value = execute_result
    chain.upsert.return_value = chain

    mock_db = MagicMock(spec=Client)
    mock_db.table.return_value = chain
    return mock_db


# ---------------------------------------------------------------------------
# Happy-path: two distinct jobs are upserted
# ---------------------------------------------------------------------------


def test_persist_jobs_two_jobs_calls_upsert_twice() -> None:
    """persist_jobs with 2 jobs should call upsert exactly twice."""
    mock_db = _make_mock_db()
    job_a = _make_job(source="adzuna", external_id="a1")
    job_b = _make_job(source="jooble", external_id="j1")

    result = persist_jobs([job_a, job_b], mock_db)

    assert result == 2
    assert mock_db.table.call_count == 2
    chain = mock_db.table.return_value
    assert chain.upsert.call_count == 2


# ---------------------------------------------------------------------------
# Empty list is handled gracefully — no DB calls, returns 0
# ---------------------------------------------------------------------------


def test_persist_jobs_empty_list_returns_zero() -> None:
    """persist_jobs with an empty list must return 0 without touching the DB."""
    mock_db = _make_mock_db()

    result = persist_jobs([], mock_db)

    assert result == 0
    mock_db.table.assert_not_called()


# ---------------------------------------------------------------------------
# Dedup: calling twice with the same job issues two upsert calls, both
# targeting the same (source, external_id).  The DB constraint handles the
# actual dedup; the test verifies the upsert call, not the DB behaviour.
# ---------------------------------------------------------------------------


def test_persist_jobs_dedup_upsert_called_with_same_key() -> None:
    """Calling persist_jobs twice with the same job should upsert with the same key."""
    mock_db = _make_mock_db()
    job = _make_job(source="adzuna", external_id="dupe-99")

    persist_jobs([job], mock_db)
    persist_jobs([job], mock_db)

    chain = mock_db.table.return_value
    assert chain.upsert.call_count == 2

    # Both calls should carry source="adzuna" and external_id="dupe-99"
    for upsert_call in chain.upsert.call_args_list:
        row_arg = upsert_call.args[0]
        assert row_arg["source"] == "adzuna"
        assert row_arg["external_id"] == "dupe-99"


# ---------------------------------------------------------------------------
# date_fetched is set; scoring fields are absent from the upserted row
# ---------------------------------------------------------------------------


def test_persist_jobs_sets_date_fetched_and_omits_score_fields() -> None:
    """Each upserted row must include date_fetched but not raw_score/llm_* fields."""
    mock_db = _make_mock_db()
    job = _make_job()

    persist_jobs([job], mock_db)

    chain = mock_db.table.return_value
    row_arg = chain.upsert.call_args.args[0]

    assert "date_fetched" in row_arg
    assert row_arg["date_fetched"]  # non-empty string

    assert "raw_score" not in row_arg
    assert "llm_score" not in row_arg
    assert "llm_rationale" not in row_arg


# ---------------------------------------------------------------------------
# on_conflict kwarg is passed correctly so Postgres knows the conflict target
# ---------------------------------------------------------------------------


def test_persist_jobs_upsert_uses_correct_on_conflict() -> None:
    """upsert must be called with on_conflict='source,external_id'."""
    mock_db = _make_mock_db()
    job = _make_job()

    persist_jobs([job], mock_db)

    chain = mock_db.table.return_value
    _, kwargs = chain.upsert.call_args
    assert kwargs.get("on_conflict") == "source,external_id"
