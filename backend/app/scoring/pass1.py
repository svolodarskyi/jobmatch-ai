"""Pass 1 weighted scoring engine.

Pure function module — no I/O, no database calls, no network calls.
Takes a Job and a Profile and returns a 0–100 composite match score
with a per-component breakdown.
"""

from app.models import Profile
from app.sources.normalize import Job

# Seniority level groupings
_SENIORITY_MAP: dict[str, str] = {
    "junior": "junior",
    "jr": "junior",
    "senior": "senior",
    "sr": "senior",
    "lead": "senior",
    "mid": "mid",
    "intermediate": "mid",
}

# Adjacency: levels that are "one step away" from each other
_ADJACENT: dict[str, set[str]] = {
    "junior": {"mid"},
    "mid": {"junior", "senior"},
    "senior": {"mid"},
}


def _skills_score(job: Job, profile: Profile) -> float:
    """Skills overlap: max 40 points.

    For each skill in profile.skills, check case-insensitive presence in
    the concatenation of job.title and job.description.  Score is
    proportional to the fraction of matched skills, capped at 40.
    """
    if not profile.skills:
        return 0.0

    text = " ".join(filter(None, [job.title, job.description])).lower()
    matches = sum(1 for skill in profile.skills if skill.lower() in text)
    return min((matches / len(profile.skills)) * 40.0, 40.0)


def _seniority_score(job: Job, profile: Profile) -> float:
    """Seniority match: max 20 points.

    If profile.seniority is None → 0.
    Exact level match → 20, adjacent level → 10, otherwise → 10 (neutral).
    """
    if profile.seniority is None:
        return 0.0

    profile_level = _SENIORITY_MAP.get(profile.seniority.lower())
    if profile_level is None:
        # Unrecognised seniority in profile — neutral
        return 10.0

    title = (job.title or "").lower()
    job_level: str | None = None
    for keyword, level in _SENIORITY_MAP.items():
        if keyword in title.split() or f" {keyword}" in title or title.startswith(keyword):
            job_level = level
            break

    if job_level is None:
        # Can't determine job seniority — neutral
        return 10.0

    if job_level == profile_level:
        return 20.0

    if job_level in _ADJACENT.get(profile_level, set()):
        return 10.0

    return 0.0


def _location_score(job: Job, profile: Profile) -> float:
    """Location / remote fit: max 20 points.

    - If any profile.locations appears (case-insensitive) in job.location → 20.
    - If job.location contains "remote" and profile preferences include
      remote → 20.
    - No match → 0.
    - profile.locations is empty → 10 (neutral).
    """
    if not profile.locations:
        return 10.0

    job_location = (job.location or "").lower()

    # Direct location match
    for loc in profile.locations:
        if loc.lower() in job_location:
            return 20.0

    # Remote match
    remote_pref = profile.preferences.get("remote")
    if "remote" in job_location and remote_pref:
        return 20.0

    return 0.0


def _salary_score(job: Job, profile: Profile) -> float:
    """Salary range overlap: max 20 points.

    If either side has no salary info → 10 (neutral).
    If ranges overlap → 20, partial overlap → 10, no overlap → 0.

    "Partial overlap" is defined as one range's endpoint landing inside
    the other range.  Full containment counts as overlap (20).
    """
    job_min = job.salary_min
    job_max = job.salary_max
    prof_min = profile.salary_min
    prof_max = profile.salary_max

    # If no salary info on either side → neutral
    if (job_min is None and job_max is None) or (prof_min is None and prof_max is None):
        return 10.0

    # Treat missing endpoints as the known endpoint (point salary)
    j_lo = job_min if job_min is not None else job_max
    j_hi = job_max if job_max is not None else job_min
    p_lo = prof_min if prof_min is not None else prof_max
    p_hi = prof_max if prof_max is not None else prof_min

    # Guaranteed non-None at this point (one side had at least one value)
    assert j_lo is not None and j_hi is not None
    assert p_lo is not None and p_hi is not None

    # Ensure lo <= hi
    j_lo, j_hi = min(j_lo, j_hi), max(j_lo, j_hi)
    p_lo, p_hi = min(p_lo, p_hi), max(p_lo, p_hi)

    # No overlap
    if j_hi < p_lo or p_hi < j_lo:
        return 0.0

    # Full containment or exact overlap
    overlap_lo = max(j_lo, p_lo)
    overlap_hi = min(j_hi, p_hi)
    overlap = overlap_hi - overlap_lo

    j_span = j_hi - j_lo
    p_span = p_hi - p_lo

    # If both are point salaries and they match exactly → full overlap
    if j_span == 0 and p_span == 0:
        return 20.0 if j_lo == p_lo else 0.0

    # Compute overlap fraction relative to the union of the two ranges
    union = max(j_hi, p_hi) - min(j_lo, p_lo)
    if union == 0:
        return 20.0

    # Full containment: one range is entirely inside the other → full score
    job_contains_profile = j_lo <= p_lo and j_hi >= p_hi
    profile_contains_job = p_lo <= j_lo and p_hi >= j_hi
    if job_contains_profile or profile_contains_job:
        return 20.0

    fraction = overlap / union
    if fraction >= 0.5:
        return 20.0
    return 10.0


def score(job: Job, profile: Profile) -> dict[str, float]:
    """Compute a 0–100 composite match score for a job against a profile.

    Args:
        job:     Canonical ``Job`` dataclass instance.
        profile: ``Profile`` Pydantic model instance.

    Returns:
        A dict with keys ``score``, ``skills``, ``seniority``,
        ``location``, and ``salary``.  ``score`` is the 0–100 composite
        (sum of components); the rest are the raw component scores.
    """
    skills = _skills_score(job, profile)
    seniority = _seniority_score(job, profile)
    location = _location_score(job, profile)
    salary = _salary_score(job, profile)

    composite = skills + seniority + location + salary

    return {
        "score": round(min(max(composite, 0.0), 100.0), 2),
        "skills": round(skills, 2),
        "seniority": round(seniority, 2),
        "location": round(location, 2),
        "salary": round(salary, 2),
    }
