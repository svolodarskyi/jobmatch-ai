from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.routers import fetch_runs as fetch_runs_router
from app.routers import jobs as jobs_router
from app.routers import profile as profile_router
from app.routers import status as status_router
from app.scheduler import scheduler
from app.settings import settings  # noqa: F401 — validates env vars on startup


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Start the APScheduler on startup and shut it down cleanly on exit."""
    scheduler.start()
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)


app = FastAPI(lifespan=lifespan)

app.include_router(profile_router.router, prefix="/profile", tags=["profile"])
app.include_router(jobs_router.router, prefix="/jobs", tags=["jobs"])
app.include_router(status_router.router, prefix="/jobs", tags=["status"])
app.include_router(fetch_runs_router.router, prefix="/fetch-runs", tags=["fetch-runs"])


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
