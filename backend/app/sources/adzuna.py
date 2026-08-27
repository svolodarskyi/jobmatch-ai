"""Adzuna Canada job search API client.

Fetches page 1 of Canadian job listings for a given job title and returns
the raw result dicts exactly as Adzuna returns them.  Normalisation into
the canonical Job shape is handled by sources/normalize.py.
"""

import httpx

from app.settings import settings

# Canada endpoint — hardcoded; never caller-configurable per architecture rules.
_ADZUNA_URL = "https://api.adzuna.com/v1/api/jobs/ca/search/1"
_RESULTS_PER_PAGE = 50


class AdzunaError(Exception):
    """Raised when the Adzuna API returns a 4xx or 5xx response."""


async def fetch_jobs(title: str, max_days_old: int = 30) -> list[dict[str, object]]:
    """Fetch page 1 of Canadian Adzuna listings for *title*.

    Args:
        title: The job title to search for (e.g. "Data Engineer").
        max_days_old: Only return listings posted within this many days.
            Passed directly to Adzuna as the ``max_days_old`` query param.
            Defaults to 30.

    Returns:
        A list of raw job dicts from the ``results`` key of the Adzuna
        response.  Never returns ``None``; raises on failure.

    Raises:
        AdzunaError: The Adzuna API responded with a 4xx or 5xx status.
        httpx.TimeoutException: The request timed out.
        httpx.RequestError: A lower-level network error occurred.
    """
    params: dict[str, str] = {
        "app_id": settings.ADZUNA_APP_ID,
        "app_key": settings.ADZUNA_APP_KEY,
        "what": title,
        "results_per_page": str(_RESULTS_PER_PAGE),
        "max_days_old": str(max_days_old),
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(_ADZUNA_URL, params=params)

    if response.is_error:
        raise AdzunaError(
            f"Adzuna API error {response.status_code}: {response.text[:200]}"
        )

    data = response.json()
    return data["results"]  # type: ignore[no-any-return]
