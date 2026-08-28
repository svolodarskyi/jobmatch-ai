"""Tests for app.pipeline — persist_jobs and pipeline.run().

All collaborators and Supabase DB calls are mocked — no live network or
database connections. Async tests use asyncio.run() directly.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
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


def _make_mock_db(existing_job_count: int = 1) -> MagicMock:
    """Return a MagicMock that mimics the Supabase client chained call pattern.

    Supports:
    - db.table(...).upsert(...).execute()
    - db.table(...).select(..., count="exact").execute()  → .count = existing_job_count
    - db.table(...).select(...).execute()  → .data = [] (for persist_jobs existing-keys query)
    - db.table(...).update(...).eq(...).eq(...).execute()
    - db.table(...).insert(...).execute()  → .data = [{"id": "test-run-uuid"}]

    Args:
        existing_job_count: Value returned by the count query in pipeline.run()
            to simulate first-run (0) vs. subsequent-run (>0) detection.
    """
    # Result for the job count query (count=exact)
    count_result = MagicMock()
    count_result.data = []
    count_result.count = existing_job_count

    # Result for fetch_run insert — supplies a run_id
    insert_result = MagicMock()
    insert_result.data = [{"id": "test-run-uuid"}]

    # Generic result for all other calls (upsert, select for existing keys, update, eq chains)
    generic_result = MagicMock()
    generic_result.data = []
    generic_result.count = None

    # We need execute() to return different things depending on context.
    # Use a single chain mock and have execute vary by call order.
    # Simplest: track calls on the chain and return count_result for the first
    # select(..., count=...) call, insert_result for the first insert call, and
    # generic_result otherwise.
    _call_index: list[int] = [0]

    class _Chain(MagicMock):
        def execute(self):  # type: ignore[override]
            # If this chain was built via insert(), return insert_result
            if getattr(self, "_is_insert", False):
                return insert_result
            # If this chain was built via select with count, return count_result
            if getattr(self, "_is_count_select", False):
                return count_result
            return generic_result

    chain = _Chain()
    chain.upsert.return_value = chain
    chain.update.return_value = chain
    chain.eq.return_value = chain
    chain.insert.side_effect = lambda *a, **kw: _make_insert_chain(insert_result)
    chain.select.side_effect = lambda *a, **kw: _make_select_chain(
        count_result if kw.get("count") is not None else generic_result
    )

    mock_db = MagicMock(spec=Client)
    mock_db.table.return_value = chain
    return mock_db


def _make_insert_chain(result: MagicMock) -> MagicMock:
    """Return a chain whose execute() yields the given insert result."""
    chain = MagicMock()
    chain.execute.return_value = result
    return chain


def _make_select_chain(result: MagicMock) -> MagicMock:
    """Return a chain whose execute() yields the given select result."""
    chain = MagicMock()
    chain.execute.return_value = result
    return chain


# ---------------------------------------------------------------------------
# Happy-path: two distinct jobs are upserted
# ---------------------------------------------------------------------------


def test_persist_jobs_two_jobs_calls_upsert_twice() -> None:
    """persist_jobs with 2 jobs should call upsert exactly twice."""
    mock_db = _make_mock_db()
    job_a = _make_job(source="adzuna", external_id="a1")
    job_b = _make_job(source="jooble", external_id="j1")

    result = persist_jobs([job_a, job_b], mock_db)

    # Result is now a dict with new/updated breakdown
    assert isinstance(result, dict)
    assert result["new_total"] + result["updated_total"] == 2
    chain = mock_db.table.return_value
    assert chain.upsert.call_count == 2


# ---------------------------------------------------------------------------
# Empty list is handled gracefully — no DB calls, returns 0
# ---------------------------------------------------------------------------


def test_persist_jobs_empty_list_returns_zero() -> None:
    """persist_jobs with an empty list must return zero totals without touching the DB."""
    mock_db = _make_mock_db()

    result = persist_jobs([], mock_db)

    assert isinstance(result, dict)
    assert result["new_total"] == 0
    assert result["updated_total"] == 0
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
# New vs. updated distinction: jobs not in DB are counted as new; jobs
# whose (source, external_id) pair already exists are counted as updated.
# ---------------------------------------------------------------------------


def _make_mock_db_with_existing(existing_ids: list[tuple[str, str]]) -> MagicMock:
    """Variant of _make_mock_db where the select().execute() for existing keys
    returns rows matching the given (source, external_id) pairs.
    """
    count_result = MagicMock()
    count_result.data = []
    count_result.count = len(existing_ids)  # used for first-run detection in run()

    existing_data = [{"source": s, "external_id": e} for s, e in existing_ids]
    existing_result = MagicMock()
    existing_result.data = existing_data
    existing_result.count = None

    insert_result = MagicMock()
    insert_result.data = [{"id": "test-run-uuid"}]

    generic_result = MagicMock()
    generic_result.data = []
    generic_result.count = None

    chain = MagicMock()
    chain.upsert.return_value = chain
    chain.update.return_value = chain
    chain.eq.return_value = chain
    chain.insert.side_effect = lambda *a, **kw: _make_insert_chain(insert_result)
    chain.select.side_effect = lambda *a, **kw: _make_select_chain(
        count_result if kw.get("count") is not None else existing_result
    )

    mock_db = MagicMock(spec=Client)
    mock_db.table.return_value = chain
    return mock_db


def test_persist_jobs_new_vs_updated_distinction() -> None:
    """persist_jobs classifies each job as new or updated based on existing DB keys."""
    existing_job = _make_job(source="adzuna", external_id="existing-1")
    new_job = _make_job(source="adzuna", external_id="brand-new-2")

    mock_db = _make_mock_db_with_existing([("adzuna", "existing-1")])

    result = persist_jobs([existing_job, new_job], mock_db)

    assert result["new_total"] == 1
    assert result["updated_total"] == 1
    assert result["new"].get("adzuna", 0) == 1
    assert result["updated"].get("adzuna", 0) == 1


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


# ---------------------------------------------------------------------------
# pipeline.run() orchestration tests — all collaborators mocked
# ---------------------------------------------------------------------------

from app.models import Profile
from app.scoring.pass2 import RankedJob, RerankResult

_SAMPLE_PROFILE = Profile(
    target_titles=["Software Engineer"],
    skills=["Python", "FastAPI"],
    seniority="mid",
    locations=["Toronto"],
    salary_min=80000,
    salary_max=120000,
)


def _make_ranked_job(job: Job, llm_score: float | None = 85.0) -> RankedJob:
    return RankedJob(
        job=job,
        pass1_score=72.0,
        llm_score=llm_score,
        llm_rationale="Good skills match." if llm_score is not None else None,
    )


_PERSIST_RESULT_2 = {"new_total": 2, "updated_total": 0, "new": {"adzuna": 1, "jooble": 1}, "updated": {}}
_PERSIST_RESULT_1 = {"new_total": 1, "updated_total": 0, "new": {"adzuna": 1}, "updated": {}}


def test_pipeline_run_happy_path_returns_correct_counts() -> None:
    """pipeline.run() returns fetched/new/scored/token counts from mocked collaborators."""
    job_a = _make_job("adzuna", "a1")
    job_j = _make_job("jooble", "j1")
    ranked_jobs = [_make_ranked_job(job_a), _make_ranked_job(job_j)]
    rerank_result = RerankResult(jobs=ranked_jobs, tokens_in=200, tokens_out=40)
    mock_db = _make_mock_db(existing_job_count=1)

    with (
        patch("app.pipeline.adzuna.fetch_jobs", new=AsyncMock(return_value=[{"id": "a1"}])),
        patch("app.pipeline.jooble.fetch_jobs", new=AsyncMock(return_value=[{"id": "j1"}])),
        patch("app.pipeline.normalize_adzuna", return_value=job_a),
        patch("app.pipeline.normalize_jooble", return_value=job_j),
        patch("app.pipeline.persist_jobs", return_value=_PERSIST_RESULT_2),
        patch("app.pipeline.pass1.score", return_value={"score": 72.0}),
        patch("app.pipeline.pass2.rerank", return_value=rerank_result),
    ):
        from app.pipeline import run

        result = asyncio.run(run(_SAMPLE_PROFILE, mock_db))

    assert result["fetched"] == 2
    assert result["new"] == 2
    assert result["scored"] == 2
    assert "fetched_by_source" in result
    assert "window_days" in result
    assert result["tokens_in"] == 200
    assert result["tokens_out"] == 40
    assert "cost_usd" in result
    assert "updated" in result


def test_pipeline_run_pass2_failure_still_returns_summary() -> None:
    """When Pass 2 returns jobs with llm_score=None, pipeline completes normally."""
    job_a = _make_job("adzuna", "a1")
    ranked_jobs = [_make_ranked_job(job_a, llm_score=None)]
    rerank_result = RerankResult(jobs=ranked_jobs, tokens_in=0, tokens_out=0)
    mock_db = _make_mock_db(existing_job_count=1)

    with (
        patch("app.pipeline.adzuna.fetch_jobs", new=AsyncMock(return_value=[{"id": "a1"}])),
        patch("app.pipeline.jooble.fetch_jobs", new=AsyncMock(return_value=[])),
        patch("app.pipeline.normalize_adzuna", return_value=job_a),
        patch("app.pipeline.persist_jobs", return_value=_PERSIST_RESULT_1),
        patch("app.pipeline.pass1.score", return_value={"score": 60.0}),
        patch("app.pipeline.pass2.rerank", return_value=rerank_result),
    ):
        from app.pipeline import run

        result = asyncio.run(run(_SAMPLE_PROFILE, mock_db))

    assert result["scored"] == 1
    assert result["fetched"] == 1
    assert result["new"] == 1


def test_pipeline_run_dedup_does_not_inflate_new() -> None:
    """'new' count comes from persist_jobs — dedup returning lower count is reflected."""
    job_a = _make_job("adzuna", "dupe-1")
    ranked_jobs = [_make_ranked_job(job_a)]
    rerank_result = RerankResult(jobs=ranked_jobs, tokens_in=100, tokens_out=20)
    dedup_persist = {"new_total": 1, "updated_total": 0, "new": {"adzuna": 1}, "updated": {}}
    mock_db = _make_mock_db(existing_job_count=1)

    with (
        patch(
            "app.pipeline.adzuna.fetch_jobs",
            new=AsyncMock(return_value=[{"id": "dupe-1"}, {"id": "dupe-1"}]),
        ),
        patch("app.pipeline.jooble.fetch_jobs", new=AsyncMock(return_value=[])),
        patch("app.pipeline.normalize_adzuna", return_value=job_a),
        patch("app.pipeline.persist_jobs", return_value=dedup_persist),
        patch("app.pipeline.pass1.score", return_value={"score": 70.0}),
        patch("app.pipeline.pass2.rerank", return_value=rerank_result),
    ):
        from app.pipeline import run

        result = asyncio.run(run(_SAMPLE_PROFILE, mock_db))

    assert result["fetched"] == 2
    assert result["new"] == 1


# ---------------------------------------------------------------------------
# Adaptive fetch window: first-run vs. subsequent-run detection
# ---------------------------------------------------------------------------


def test_pipeline_first_run_uses_initial_window() -> None:
    """When DB has 0 job rows, pipeline uses FETCH_INITIAL_DAYS as max_days_old."""
    job_a = _make_job("adzuna", "a1")
    ranked_jobs = [_make_ranked_job(job_a)]
    rerank_result = RerankResult(jobs=ranked_jobs, tokens_in=100, tokens_out=20)
    # existing_job_count=0 triggers first-run path
    mock_db = _make_mock_db(existing_job_count=0)

    adzuna_mock = AsyncMock(return_value=[{"id": "a1"}])

    with (
        patch("app.pipeline.adzuna.fetch_jobs", new=adzuna_mock),
        patch("app.pipeline.jooble.fetch_jobs", new=AsyncMock(return_value=[])),
        patch("app.pipeline.normalize_adzuna", return_value=job_a),
        patch("app.pipeline.persist_jobs", return_value=_PERSIST_RESULT_1),
        patch("app.pipeline.pass1.score", return_value={"score": 72.0}),
        patch("app.pipeline.pass2.rerank", return_value=rerank_result),
    ):
        from app.pipeline import run
        from app.settings import settings

        result = asyncio.run(run(_SAMPLE_PROFILE, mock_db))

    # Verify the window reported in the result matches initial days
    assert result["window_days"] == settings.FETCH_INITIAL_DAYS
    # Verify adzuna was called with the initial window
    adzuna_mock.assert_called_once_with(
        _SAMPLE_PROFILE.target_titles[0], settings.FETCH_INITIAL_DAYS
    )


def test_pipeline_subsequent_run_uses_incremental_window() -> None:
    """When DB has existing job rows, pipeline uses FETCH_INCREMENTAL_DAYS as max_days_old."""
    job_a = _make_job("adzuna", "a1")
    ranked_jobs = [_make_ranked_job(job_a)]
    rerank_result = RerankResult(jobs=ranked_jobs, tokens_in=100, tokens_out=20)
    # existing_job_count=42 triggers subsequent-run path
    mock_db = _make_mock_db(existing_job_count=42)

    adzuna_mock = AsyncMock(return_value=[{"id": "a1"}])

    with (
        patch("app.pipeline.adzuna.fetch_jobs", new=adzuna_mock),
        patch("app.pipeline.jooble.fetch_jobs", new=AsyncMock(return_value=[])),
        patch("app.pipeline.normalize_adzuna", return_value=job_a),
        patch("app.pipeline.persist_jobs", return_value=_PERSIST_RESULT_1),
        patch("app.pipeline.pass1.score", return_value={"score": 72.0}),
        patch("app.pipeline.pass2.rerank", return_value=rerank_result),
    ):
        from app.pipeline import run
        from app.settings import settings

        result = asyncio.run(run(_SAMPLE_PROFILE, mock_db))

    # Verify the window reported in the result matches incremental days
    assert result["window_days"] == settings.FETCH_INCREMENTAL_DAYS
    # Verify adzuna was called with the incremental window
    adzuna_mock.assert_called_once_with(
        _SAMPLE_PROFILE.target_titles[0], settings.FETCH_INCREMENTAL_DAYS
    )


# ---------------------------------------------------------------------------
# fetch_run row is written: inserted at start, updated at end
# ---------------------------------------------------------------------------


def test_pipeline_run_writes_fetch_run_row() -> None:
    """pipeline.run() inserts a fetch_run row at start and updates it at end."""
    job_a = _make_job("adzuna", "a1")
    ranked_jobs = [_make_ranked_job(job_a)]
    rerank_result = RerankResult(jobs=ranked_jobs, tokens_in=150, tokens_out=30)
    mock_db = _make_mock_db(existing_job_count=1)

    with (
        patch("app.pipeline.adzuna.fetch_jobs", new=AsyncMock(return_value=[{"id": "a1"}])),
        patch("app.pipeline.jooble.fetch_jobs", new=AsyncMock(return_value=[])),
        patch("app.pipeline.normalize_adzuna", return_value=job_a),
        patch("app.pipeline.persist_jobs", return_value=_PERSIST_RESULT_1),
        patch("app.pipeline.pass1.score", return_value={"score": 72.0}),
        patch("app.pipeline.pass2.rerank", return_value=rerank_result),
    ):
        from app.pipeline import run

        result = asyncio.run(run(_SAMPLE_PROFILE, mock_db))

    # Verify the fetch_run table was touched (insert for open, update for close)
    table_calls = [call.args[0] for call in mock_db.table.call_args_list]
    assert "fetch_run" in table_calls, "fetch_run table should have been accessed"

    # The result should include instrumentation fields
    assert result["tokens_in"] == 150
    assert result["tokens_out"] == 30
    expected_cost = round((150 * 0.15 + 30 * 0.60) / 1_000_000, 6)
    assert result["cost_usd"] == expected_cost


# ---------------------------------------------------------------------------
# source_stats shape — issue #42
#
# In all three tests below, ranked jobs are built with llm_score=None so
# that step 8 never issues a "job" table .update() call. That leaves the
# mocked chain's .update() call list containing exactly one call: the final
# fetch_run stats update, whose first positional arg is the update payload
# dict passed to db.table("fetch_run").update(...).
# ---------------------------------------------------------------------------


def _get_source_stats(mock_db: MagicMock) -> dict[str, object]:
    """Extract source_stats from the fetch_run update payload captured on the
    shared mock chain (see _make_mock_db — every db.table(...) call returns
    the same chain object, so .update() calls from any table land here).
    """
    chain = mock_db.table.return_value
    for call in chain.update.call_args_list:
        payload = call.args[0]
        if "source_stats" in payload:
            return payload["source_stats"]
    raise AssertionError("no fetch_run update call with source_stats found")


def test_pipeline_source_stats_includes_zero_activity_source() -> None:
    """A source with retrieved > 0 but 0 new/0 updated still appears in
    source_stats (e.g. every raw listing was filtered out during
    normalization, so persist_jobs never saw it).
    """
    job_a = _make_job("adzuna", "a1")
    ranked_jobs = [_make_ranked_job(job_a, llm_score=None)]
    rerank_result = RerankResult(jobs=ranked_jobs, tokens_in=0, tokens_out=0)
    mock_db = _make_mock_db(existing_job_count=1)

    persist_result = {
        "new_total": 1,
        "updated_total": 0,
        "new": {"adzuna": 1},
        "updated": {},
    }

    with (
        patch("app.pipeline.adzuna.fetch_jobs", new=AsyncMock(return_value=[{"id": "a1"}])),
        patch(
            "app.pipeline.jooble.fetch_jobs",
            new=AsyncMock(return_value=[{"id": "j1"}, {"id": "j2"}]),
        ),
        patch("app.pipeline.normalize_adzuna", return_value=job_a),
        # Every raw Jooble listing is filtered out (e.g. too old) — retrieved
        # is still 2, but nothing makes it into the normalized/persisted list.
        patch("app.pipeline.normalize_jooble", return_value=None),
        patch("app.pipeline.persist_jobs", return_value=persist_result),
        patch("app.pipeline.pass1.score", return_value={"score": 72.0}),
        patch("app.pipeline.pass2.rerank", return_value=rerank_result),
    ):
        from app.pipeline import run

        asyncio.run(run(_SAMPLE_PROFILE, mock_db))

    source_stats = _get_source_stats(mock_db)
    assert source_stats["jooble"] == {"retrieved": 2, "new": 0, "updated": 0}
    assert source_stats["adzuna"] == {"retrieved": 1, "new": 1, "updated": 0}


def test_pipeline_source_stats_includes_failed_source() -> None:
    """A source whose fetch raises still appears in source_stats as all-zero,
    rather than being omitted (exercises _fetch_source's except branch).
    """
    job_a = _make_job("adzuna", "a1")
    ranked_jobs = [_make_ranked_job(job_a, llm_score=None)]
    rerank_result = RerankResult(jobs=ranked_jobs, tokens_in=0, tokens_out=0)
    mock_db = _make_mock_db(existing_job_count=1)

    persist_result = {
        "new_total": 1,
        "updated_total": 0,
        "new": {"adzuna": 1},
        "updated": {},
    }

    with (
        patch("app.pipeline.adzuna.fetch_jobs", new=AsyncMock(return_value=[{"id": "a1"}])),
        patch(
            "app.pipeline.jooble.fetch_jobs",
            new=AsyncMock(side_effect=RuntimeError("jooble is down")),
        ),
        patch("app.pipeline.normalize_adzuna", return_value=job_a),
        patch("app.pipeline.persist_jobs", return_value=persist_result),
        patch("app.pipeline.pass1.score", return_value={"score": 72.0}),
        patch("app.pipeline.pass2.rerank", return_value=rerank_result),
    ):
        from app.pipeline import run

        asyncio.run(run(_SAMPLE_PROFILE, mock_db))

    source_stats = _get_source_stats(mock_db)
    assert source_stats["jooble"] == {"retrieved": 0, "new": 0, "updated": 0}
    assert source_stats["adzuna"] == {"retrieved": 1, "new": 1, "updated": 0}


def test_pipeline_source_stats_retrieved_differs_from_new_on_dupes() -> None:
    """retrieved counts raw listings before dedup, so it can exceed new+updated
    when some retrieved listings are already-known duplicates that get
    dropped entirely (only some become 'updated' rows).
    """
    job_a = _make_job("adzuna", "a1")
    ranked_jobs = [_make_ranked_job(job_a, llm_score=None)]
    rerank_result = RerankResult(jobs=ranked_jobs, tokens_in=0, tokens_out=0)
    mock_db = _make_mock_db(existing_job_count=1)

    # 5 raw listings retrieved from Adzuna; persist_jobs reports 2 new + 3
    # updated (retrieved > new, and retrieved != new).
    persist_result = {
        "new_total": 2,
        "updated_total": 3,
        "new": {"adzuna": 2},
        "updated": {"adzuna": 3},
    }

    with (
        patch(
            "app.pipeline.adzuna.fetch_jobs",
            new=AsyncMock(
                return_value=[{"id": f"a{i}"} for i in range(5)],
            ),
        ),
        patch("app.pipeline.jooble.fetch_jobs", new=AsyncMock(return_value=[])),
        patch("app.pipeline.normalize_adzuna", return_value=job_a),
        patch("app.pipeline.persist_jobs", return_value=persist_result),
        patch("app.pipeline.pass1.score", return_value={"score": 72.0}),
        patch("app.pipeline.pass2.rerank", return_value=rerank_result),
    ):
        from app.pipeline import run

        asyncio.run(run(_SAMPLE_PROFILE, mock_db))

    source_stats = _get_source_stats(mock_db)
    assert source_stats["adzuna"] == {"retrieved": 5, "new": 2, "updated": 3}
    assert source_stats["adzuna"]["retrieved"] != source_stats["adzuna"]["new"]


def test_pipeline_source_stats_empty_when_no_titles() -> None:
    """When profile.target_titles is empty, no fetch is attempted and
    source_stats stays {} — no synthetic entries for unqueried sources.
    """
    empty_profile = Profile(
        target_titles=[],
        skills=["Python"],
        seniority="mid",
        locations=["Toronto"],
    )
    rerank_result = RerankResult(jobs=[], tokens_in=0, tokens_out=0)
    mock_db = _make_mock_db(existing_job_count=1)

    with (
        patch("app.pipeline.persist_jobs", return_value=_PERSIST_RESULT_1),
        patch("app.pipeline.pass1.score", return_value={"score": 72.0}),
        patch("app.pipeline.pass2.rerank", return_value=rerank_result),
    ):
        from app.pipeline import run

        asyncio.run(run(empty_profile, mock_db))

    source_stats = _get_source_stats(mock_db)
    assert source_stats == {}


# ---------------------------------------------------------------------------
# fetch_run marked status="error" on unhandled exception — issue #44
#
# Distinct from status="partial" (per-source fetch failures handled inline
# by _fetch_source, or Pass 2 misses) — this covers an exception that
# escapes that handling entirely, e.g. a DB write failure in persist_jobs.
# ---------------------------------------------------------------------------


def test_pipeline_run_marks_fetch_run_error_on_unhandled_exception() -> None:
    """An exception raised after run_id is obtained (e.g. persist_jobs failing)
    must propagate to the caller AND update fetch_run with status="error",
    a non-null completed_at, and error_message set — without any of the
    "success" fields (fetched_total, source_stats, etc.) in that payload.
    """
    mock_db = _make_mock_db(existing_job_count=1)
    boom = RuntimeError("persist_jobs blew up")

    with (
        patch("app.pipeline.adzuna.fetch_jobs", new=AsyncMock(return_value=[{"id": "a1"}])),
        patch("app.pipeline.jooble.fetch_jobs", new=AsyncMock(return_value=[])),
        patch("app.pipeline.normalize_adzuna", return_value=_make_job("adzuna", "a1")),
        patch("app.pipeline.persist_jobs", side_effect=boom),
    ):
        from app.pipeline import run

        with pytest.raises(RuntimeError, match="persist_jobs blew up"):
            asyncio.run(run(_SAMPLE_PROFILE, mock_db))

    chain = mock_db.table.return_value
    error_payloads = [
        call.args[0]
        for call in chain.update.call_args_list
        if call.args[0].get("status") == "error"
    ]
    assert len(error_payloads) == 1, "expected exactly one status='error' fetch_run update"
    payload = error_payloads[0]

    assert payload["status"] == "error"
    assert payload["completed_at"]  # non-empty string
    assert "persist_jobs blew up" in payload["error_message"]

    # None of the success-path fields were guessed/partially written.
    for field in (
        "fetched_total",
        "new_jobs",
        "updated_jobs",
        "scored_pass1",
        "scored_pass2",
        "source_stats",
        "tokens_in",
        "tokens_out",
        "cost_usd",
    ):
        assert field not in payload


def test_pipeline_run_no_op_when_fetch_run_insert_failed() -> None:
    """If the initial fetch_run insert itself fails to yield a run_id, the
    exception still propagates but no fetch_run update is attempted — there
    is no row to mark. This is a deliberate no-op, not a bug.
    """
    mock_db = _make_mock_db(existing_job_count=1)
    # Force the fetch_run insert to return no data, so run_id stays None.
    no_row_insert_result = MagicMock()
    no_row_insert_result.data = []
    chain = mock_db.table.return_value
    chain.insert.side_effect = lambda *a, **kw: _make_insert_chain(no_row_insert_result)

    boom = RuntimeError("persist_jobs blew up")

    with (
        patch("app.pipeline.adzuna.fetch_jobs", new=AsyncMock(return_value=[{"id": "a1"}])),
        patch("app.pipeline.jooble.fetch_jobs", new=AsyncMock(return_value=[])),
        patch("app.pipeline.normalize_adzuna", return_value=_make_job("adzuna", "a1")),
        patch("app.pipeline.persist_jobs", side_effect=boom),
    ):
        from app.pipeline import run

        with pytest.raises(RuntimeError, match="persist_jobs blew up"):
            asyncio.run(run(_SAMPLE_PROFILE, mock_db))

    assert chain.update.call_args_list == []
