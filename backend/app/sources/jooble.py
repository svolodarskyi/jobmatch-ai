"""Jooble API client — Canada-only job listing fetcher."""

import httpx

from app.settings import settings

_JOOBLE_BASE_URL = "https://jooble.org/api"


class JoobleError(Exception):
    """Raised when the Jooble API returns an error response."""


async def fetch_jobs(title: str) -> list[dict[str, object]]:
    """Fetch Canadian job listings from Jooble for the given job title.

    Args:
        title: Job title / keywords to search for.

    Returns:
        List of raw job dicts as returned by the Jooble API.

    Raises:
        JoobleError: On a 4xx or 5xx HTTP response, or if the response body
            does not contain a "jobs" key.
        httpx.HTTPError: On a network or timeout error.
    """
    url = f"{_JOOBLE_BASE_URL}/{settings.JOOBLE_API_KEY}"
    payload = {
        "keywords": title,
        "location": "Canada",
        "country": "CA",  # Canada-only — not caller-configurable
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload)

    if response.is_error:
        raise JoobleError(
            f"Jooble API returned HTTP {response.status_code}: {response.text[:200]}"
        )

    data = response.json()

    if "jobs" not in data:
        raise JoobleError(
            f"Jooble API response missing 'jobs' key. Keys present: {list(data.keys())}"
        )

    jobs: list[dict[str, object]] = data["jobs"]
    return jobs
