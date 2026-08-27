from fastapi import FastAPI

from app.routers import jobs as jobs_router
from app.routers import profile as profile_router
from app.settings import settings  # noqa: F401 — validates env vars on startup

app = FastAPI()

app.include_router(profile_router.router, prefix="/profile", tags=["profile"])
app.include_router(jobs_router.router, prefix="/jobs", tags=["jobs"])


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
