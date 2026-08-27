"""Tests for the Adzuna API client (app/sources/adzuna.py).

All HTTP calls are intercepted by respx — no live network calls are made.
The async fetch_jobs coroutine is exercised via asyncio.run so no additional
pytest plugin (pytest-anyio, pytest-asyncio) is required.
"""

import asyncio
import json
from pathlib import Path

import pytest
import respx
from httpx import Response

from app.sources.adzuna import AdzunaError, fetch_jobs

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FIXTURES_DIR = Path(__file__).parent / "fixtures"
_ADZUNA_URL = "https://api.adzuna.com/v1/api/jobs/ca/search/1"


def _load_fixture(name: str) -> dict:
    return json.loads((_FIXTURES_DIR / name).read_text())


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_fetch_jobs_happy_path_returns_results():
    """Happy path: a 200 response returns the list of result dicts."""
    fixture = _load_fixture("adzuna_sample.json")

    with respx.mock:
        respx.get(_ADZUNA_URL).mock(return_value=Response(200, json=fixture))
        results = asyncio.run(fetch_jobs("Senior Data Engineer"))

    assert isinstance(results, list)
    assert len(results) == 1
    job = results[0]
    assert job["id"] == "adzuna-123"
    assert job["title"] == "Senior Data Engineer"
    assert job["company"]["display_name"] == "Acme Corp"


def test_fetch_jobs_passes_title_as_what_param():
    """The 'what' query param must match the title argument."""
    fixture = _load_fixture("adzuna_sample.json")

    with respx.mock:
        route = respx.get(_ADZUNA_URL).mock(
            return_value=Response(200, json=fixture)
        )
        asyncio.run(fetch_jobs("Data Analyst"))

    assert route.called
    sent_request = route.calls.last.request
    assert sent_request.url.params["what"] == "Data Analyst"


def test_fetch_jobs_401_raises_adzuna_error():
    """A 401 Unauthorized response must raise AdzunaError."""
    with respx.mock:
        respx.get(_ADZUNA_URL).mock(return_value=Response(401, text="Unauthorized"))

        with pytest.raises(AdzunaError):
            asyncio.run(fetch_jobs("Software Engineer"))


def test_fetch_jobs_500_raises_adzuna_error():
    """A 500 Internal Server Error response must raise AdzunaError."""
    with respx.mock:
        respx.get(_ADZUNA_URL).mock(
            return_value=Response(500, text="Internal Server Error")
        )

        with pytest.raises(AdzunaError):
            asyncio.run(fetch_jobs("Backend Developer"))
