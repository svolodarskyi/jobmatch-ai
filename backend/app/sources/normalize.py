"""Pure normalizer functions for source API payloads.

Maps raw dicts from Adzuna and Jooble into the canonical ``Job`` shape.
This module performs no I/O, network calls, or database access.

Missing optional fields normalise to ``None``.
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class Job:
    source: str
    external_id: str
    title: str | None
    company: str | None
    location: str | None
    salary_min: int | None
    salary_max: int | None
    description: str | None
    url: str | None


def normalize_adzuna(raw: dict[str, Any]) -> Job:
    """Map a raw Adzuna result dict to a canonical ``Job``.

    Args:
        raw: A single entry from the ``results`` list returned by the
             Adzuna Canada API.

    Returns:
        A populated ``Job`` dataclass instance.
    """
    salary_min_raw = raw.get("salary_min")
    salary_max_raw = raw.get("salary_max")

    company_obj: dict[str, Any] = raw.get("company") or {}
    location_obj: dict[str, Any] = raw.get("location") or {}

    return Job(
        source="adzuna",
        external_id=raw["id"],
        title=raw.get("title"),
        company=company_obj.get("display_name"),
        location=location_obj.get("display_name"),
        salary_min=int(salary_min_raw) if salary_min_raw is not None else None,
        salary_max=int(salary_max_raw) if salary_max_raw is not None else None,
        description=raw.get("description"),
        url=raw.get("redirect_url"),
    )


def normalize_jooble(raw: dict[str, Any]) -> Job:
    """Map a raw Jooble result dict to a canonical ``Job``.

    Jooble exposes a single ``salary`` string field (e.g. ``"85000"`` or
    ``"$85,000 a year"``).  We attempt to parse it as an integer for
    ``salary_min``; on failure (non-numeric or absent) both ``salary_min``
    and ``salary_max`` are ``None``.

    Args:
        raw: A single entry from the ``jobs`` list returned by the
             Jooble Canada API.

    Returns:
        A populated ``Job`` dataclass instance.
    """
    salary_raw = raw.get("salary")
    salary_min: int | None = None
    if salary_raw is not None:
        try:
            salary_min = int(salary_raw)
        except (ValueError, TypeError):
            salary_min = None

    return Job(
        source="jooble",
        external_id=raw["id"],
        title=raw.get("title"),
        company=raw.get("company"),
        location=raw.get("location"),
        salary_min=salary_min,
        salary_max=None,
        description=raw.get("snippet"),
        url=raw.get("link"),
    )
