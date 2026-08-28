"""Pure normalizer functions for source API payloads.

Maps raw dicts from Adzuna and Jooble into the canonical ``Job`` shape.
This module performs no I/O, network calls, or database access.

Missing optional fields normalise to ``None``.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


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
    date_posted: datetime | None = None


def _parse_adzuna_created(raw: Any) -> datetime | None:
    """Parse Adzuna's ``created`` field into a timezone-aware ``datetime``.

    Adzuna returns ISO 8601 timestamps (e.g. ``"2024-01-15T10:00:00Z"``).
    Returns ``None`` if *raw* is ``None`` or unparseable.
    """
    if raw is None:
        return None
    try:
        dt = datetime.fromisoformat(str(raw))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


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
        date_posted=_parse_adzuna_created(raw.get("created")),
    )


def _parse_jooble_updated(raw: Any) -> datetime | None:
    """Parse Jooble's ``updated`` field into a timezone-aware ``datetime``.

    Jooble returns timestamps like ``"2024-01-15T10:00:00.0000000"`` — strip
    sub-second precision beyond 6 digits before calling
    ``datetime.fromisoformat``. Returns ``None`` if *raw* is ``None`` or
    unparseable.
    """
    if raw is None:
        return None
    try:
        updated_str = str(raw)
        # Remove trailing fractional seconds beyond microseconds
        if "." in updated_str:
            base, frac = updated_str.split(".", 1)
            frac = frac[:6]
            updated_str = f"{base}.{frac}"
        updated_dt = datetime.fromisoformat(updated_str)
    except (ValueError, TypeError):
        return None
    if updated_dt.tzinfo is None:
        updated_dt = updated_dt.replace(tzinfo=UTC)
    return updated_dt


def normalize_jooble(raw: dict[str, Any], max_days_old: int | None = None) -> Job | None:
    """Map a raw Jooble result dict to a canonical ``Job``.

    Jooble exposes a single ``salary`` string field (e.g. ``"85000"`` or
    ``"$85,000 a year"``).  We attempt to parse it as an integer for
    ``salary_min``; on failure (non-numeric or absent) both ``salary_min``
    and ``salary_max`` are ``None``.

    If ``max_days_old`` is provided and the listing has an ``updated`` field,
    listings older than ``max_days_old`` days are dropped (return ``None``).

    Args:
        raw: A single entry from the ``jobs`` list returned by the
             Jooble Canada API.
        max_days_old: Optional age filter in days.  When provided, listings
            whose ``updated`` timestamp is older than this many days are
            skipped.

    Returns:
        A populated ``Job`` dataclass instance, or ``None`` if the listing
        is filtered out by the date window.
    """
    updated_raw = raw.get("updated")
    date_posted = _parse_jooble_updated(updated_raw)

    # ------------------------------------------------------------------
    # Date filter: drop stale Jooble listings when max_days_old is set
    # ------------------------------------------------------------------
    if max_days_old is not None and updated_raw is not None:
        if date_posted is not None:
            age_days = (datetime.now(UTC) - date_posted).days
            if age_days > max_days_old:
                logger.debug(
                    "Jooble listing %s skipped — %d days old (window: %d)",
                    raw.get("id"),
                    age_days,
                    max_days_old,
                )
                return None
        else:
            logger.warning(
                "Jooble listing %s has unparseable 'updated' field: %r",
                raw.get("id"),
                updated_raw,
            )

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
        date_posted=date_posted,
    )
