"""APScheduler wiring for the daily fetch pipeline.

The module exposes a single ``AsyncIOScheduler`` instance (``scheduler``) and a
``scheduled_fetch`` coroutine that the scheduler calls on the configured
interval.  ``scheduled_fetch`` is kept as a plain module-level async function
so tests can call it directly without touching the scheduler.

Lifecycle (start / stop) is handled by the FastAPI lifespan in ``main.py``.
"""

import logging
from typing import Any, cast

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from supabase import create_client

from app import pipeline
from app.models import Profile
from app.settings import settings

logger = logging.getLogger(__name__)

#: The global scheduler instance.  ``main.py`` starts and stops it via the
#: FastAPI lifespan context manager.
scheduler: AsyncIOScheduler = AsyncIOScheduler()


async def scheduled_fetch() -> None:
    """Fetch + score jobs on a timer.

    Steps:
    1. Create a fresh Supabase client for this run.
    2. Load the single user profile from the ``profile`` table.
    3. If no profile exists, log a warning and return (no exception).
    4. Otherwise delegate to ``pipeline.run(profile, db)``.
    """
    db = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)

    result = db.table("profile").select("*").execute()
    rows = result.data
    if not rows:
        logger.warning("Scheduled fetch skipped: no profile found in DB.")
        return

    profile = Profile(**cast(dict[str, Any], rows[0]))
    logger.info("Scheduled fetch starting for profile with titles: %s", profile.target_titles)
    summary = await pipeline.run(profile, db)
    logger.info("Scheduled fetch complete: %s", summary)


def register_jobs(sched: AsyncIOScheduler) -> None:
    """Register the ``scheduled_fetch`` job on *sched*.

    Separated from module-level code so tests can create a fresh scheduler,
    call this function, and inspect the job list without side effects.
    """
    sched.add_job(
        scheduled_fetch,
        trigger="interval",
        hours=settings.FETCH_INTERVAL_HOURS,
        id="pipeline_fetch",
        replace_existing=True,
    )


# Register on the module-level scheduler at import time.
register_jobs(scheduler)
