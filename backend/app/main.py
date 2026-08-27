from fastapi import FastAPI

from app.settings import settings  # noqa: F401 — validates env vars on startup

app = FastAPI()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
