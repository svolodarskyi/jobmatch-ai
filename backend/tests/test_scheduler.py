"""Tests for app/scheduler.py — job registration and scheduled_fetch behaviour.

No live network or DB calls are made here.  pipeline.run and the Supabase
client are fully mocked.
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app import scheduler as scheduler_module
from app.models import Profile
from app.scheduler import register_jobs, scheduled_fetch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db(rows: list[dict]) -> MagicMock:  # type: ignore[type-arg]
    """Return a mock Supabase client whose profile table yields *rows*."""
    execute_result = SimpleNamespace(data=rows)
    select_mock = MagicMock()
    select_mock.execute.return_value = execute_result
    table_mock = MagicMock()
    table_mock.select.return_value = select_mock
    db = MagicMock()
    db.table.return_value = table_mock
    return db


# ---------------------------------------------------------------------------
# Job registration
# ---------------------------------------------------------------------------

class TestRegisterJobs:
    def test_exactly_one_job_registered(self) -> None:
        """register_jobs adds exactly one job to the given scheduler."""
        sched = AsyncIOScheduler()
        register_jobs(sched)
        jobs = sched.get_jobs()
        assert len(jobs) == 1

    def test_job_id_is_pipeline_fetch(self) -> None:
        sched = AsyncIOScheduler()
        register_jobs(sched)
        job = sched.get_jobs()[0]
        assert job.id == "pipeline_fetch"

    def test_job_func_is_scheduled_fetch(self) -> None:
        """The registered callable must be scheduler_module.scheduled_fetch."""
        sched = AsyncIOScheduler()
        register_jobs(sched)
        job = sched.get_jobs()[0]
        assert job.func is scheduled_fetch

    def test_module_level_scheduler_has_pipeline_fetch(self) -> None:
        """The module-level scheduler already has the job wired up."""
        job_ids = [j.id for j in scheduler_module.scheduler.get_jobs()]
        assert "pipeline_fetch" in job_ids


# ---------------------------------------------------------------------------
# scheduled_fetch — no profile case
# ---------------------------------------------------------------------------

class TestScheduledFetchNoProfile:
    def test_skips_gracefully_when_no_profile(self) -> None:
        """scheduled_fetch must not raise when the profile table is empty."""
        mock_db = _make_db([])

        with (
            patch("app.scheduler.create_client", return_value=mock_db),
            patch("app.scheduler.pipeline.run", new_callable=AsyncMock) as mock_run,
        ):
            # Must complete without exception
            asyncio.run(scheduled_fetch())
            mock_run.assert_not_called()


# ---------------------------------------------------------------------------
# scheduled_fetch — profile exists case
# ---------------------------------------------------------------------------

class TestScheduledFetchWithProfile:
    def test_calls_pipeline_run_with_profile(self) -> None:
        """scheduled_fetch calls pipeline.run exactly once with the loaded profile."""
        profile_row = {
            "target_titles": ["Software Engineer"],
            "skills": ["Python"],
            "seniority": "mid",
            "locations": ["Toronto"],
            "salary_min": 80000,
            "salary_max": 120000,
            "preferences": {},
        }
        mock_db = _make_db([profile_row])

        with (
            patch("app.scheduler.create_client", return_value=mock_db),
            patch("app.scheduler.pipeline.run", new_callable=AsyncMock) as mock_run,
        ):
            asyncio.run(scheduled_fetch())

            mock_run.assert_awaited_once()
            call_args = mock_run.call_args
            passed_profile = call_args.args[0]
            assert isinstance(passed_profile, Profile)
            assert passed_profile.target_titles == ["Software Engineer"]
            # DB client is passed as second argument
            assert call_args.args[1] is mock_db

    def test_pipeline_run_return_value_is_not_raised(self) -> None:
        """scheduled_fetch does not raise even if pipeline.run returns a summary."""
        profile_row: dict[str, object] = {
            "target_titles": [],
            "skills": [],
            "seniority": None,
            "locations": [],
            "salary_min": None,
            "salary_max": None,
            "preferences": {},
        }
        mock_db = _make_db([profile_row])

        with (
            patch("app.scheduler.create_client", return_value=mock_db),
            patch(
                "app.scheduler.pipeline.run",
                new_callable=AsyncMock,
                return_value={"fetched": 10, "new": 5, "scored": 3},
            ),
        ):
            # Should not raise
            asyncio.run(scheduled_fetch())
