"""Tests for the Jooble API client (backend/app/sources/jooble.py).

All HTTP calls are intercepted by respx — no live network calls are made.
"""

import json
from pathlib import Path

import pytest
import respx
from httpx import Response

from app.settings import settings
from app.sources.jooble import JoobleError, fetch_jobs

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "jooble_sample.json"

_JOOBLE_URL = f"https://jooble.org/api/{settings.JOOBLE_API_KEY}"


def _load_fixture() -> dict:
    return json.loads(FIXTURE_PATH.read_text())


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
@respx.mock
async def test_fetch_jobs_happy_path() -> None:
    """fetch_jobs returns a list of raw job dicts on a successful response."""
    fixture = _load_fixture()
    respx.post(_JOOBLE_URL).mock(return_value=Response(200, json=fixture))

    jobs = await fetch_jobs("Data Engineer")

    assert isinstance(jobs, list)
    assert len(jobs) == 1
    job = jobs[0]
    assert job["id"] == "jooble-456"
    assert job["title"] == "Data Engineer"
    assert job["company"] == "Tech Solutions Inc"
    assert job["location"] == "Calgary, AB"


@pytest.mark.anyio
@respx.mock
async def test_fetch_jobs_sends_canada_payload() -> None:
    """fetch_jobs hardcodes Canada-only parameters in the request body."""
    fixture = _load_fixture()
    route = respx.post(_JOOBLE_URL).mock(return_value=Response(200, json=fixture))

    await fetch_jobs("Software Engineer")

    # Inspect the actual request that was sent
    request = route.calls.last.request
    body = json.loads(request.content)
    assert body["country"] == "CA"
    assert body["location"] == "Canada"
    assert body["keywords"] == "Software Engineer"


@pytest.mark.anyio
@respx.mock
async def test_fetch_jobs_raises_on_4xx() -> None:
    """fetch_jobs raises JoobleError on a 4xx response."""
    respx.post(_JOOBLE_URL).mock(return_value=Response(401, text="Unauthorized"))

    with pytest.raises(JoobleError, match="401"):
        await fetch_jobs("Data Engineer")


@pytest.mark.anyio
@respx.mock
async def test_fetch_jobs_raises_on_5xx() -> None:
    """fetch_jobs raises JoobleError on a 5xx response."""
    respx.post(_JOOBLE_URL).mock(return_value=Response(500, text="Internal Server Error"))

    with pytest.raises(JoobleError, match="500"):
        await fetch_jobs("Data Engineer")


@pytest.mark.anyio
@respx.mock
async def test_fetch_jobs_raises_on_missing_jobs_key() -> None:
    """fetch_jobs raises JoobleError when the response has no 'jobs' key."""
    respx.post(_JOOBLE_URL).mock(return_value=Response(200, json={"totalCount": 0}))

    with pytest.raises(JoobleError, match="jobs"):
        await fetch_jobs("Data Engineer")
