"""Pure unit tests for backend/app/scoring/pass1.py.

No fixtures, no mocking — pass1.score() is a pure function.
"""

from app.models import Profile
from app.scoring.pass1 import score
from app.sources.normalize import Job

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _job(**kwargs) -> Job:
    defaults: dict = {
        "source": "adzuna",
        "external_id": "1",
        "title": "Software Engineer",
        "company": "Acme",
        "location": "Toronto, ON",
        "salary_min": 80_000,
        "salary_max": 120_000,
        "description": "We use Python, Django, and PostgreSQL.",
        "url": "https://example.com/job/1",
    }
    defaults.update(kwargs)
    return Job(**defaults)


def _profile(**kwargs) -> Profile:
    defaults: dict = {
        "target_titles": ["Software Engineer"],
        "skills": ["Python", "Django", "PostgreSQL"],
        "seniority": "senior",
        "locations": ["Toronto"],
        "salary_min": 90_000,
        "salary_max": 130_000,
        "preferences": {},
    }
    defaults.update(kwargs)
    return Profile(**defaults)


# ---------------------------------------------------------------------------
# Return shape
# ---------------------------------------------------------------------------

def test_return_shape():
    result = score(_job(), _profile())
    assert set(result.keys()) == {"score", "skills", "seniority", "location", "salary"}


# ---------------------------------------------------------------------------
# Skills component
# ---------------------------------------------------------------------------

def test_skills_full_overlap():
    """All three profile skills appear in job title/description → 40 pts."""
    job = _job(
        title="Senior Python Django Developer",
        description="Must know PostgreSQL and Django deeply.",
    )
    profile = _profile(skills=["Python", "Django", "PostgreSQL"])
    result = score(job, profile)
    assert result["skills"] == 40.0


def test_skills_no_overlap():
    """No profile skills appear in job text → 0 pts."""
    job = _job(title="Java Spring Developer", description="We use Kafka and Spring Boot.")
    profile = _profile(skills=["Python", "Django", "PostgreSQL"])
    result = score(job, profile)
    assert result["skills"] == 0.0


def test_skills_empty_profile():
    """Profile has no skills → skills component is 0."""
    result = score(_job(), _profile(skills=[]))
    assert result["skills"] == 0.0


def test_skills_partial_overlap():
    """Partial match is proportional: 1 of 3 skills → 40/3 ≈ 13.33."""
    job = _job(title="Python Developer", description="Python is required.")
    profile = _profile(skills=["Python", "Django", "PostgreSQL"])
    result = score(job, profile)
    assert abs(result["skills"] - 40 / 3) < 0.1


def test_skills_case_insensitive():
    """Skill matching is case-insensitive."""
    job = _job(title="python developer", description="use DJANGO daily.")
    profile = _profile(skills=["Python", "Django"])
    result = score(job, profile)
    assert result["skills"] == 40.0


# ---------------------------------------------------------------------------
# Seniority component
# ---------------------------------------------------------------------------

def test_seniority_exact_match():
    """Job title contains 'senior' and profile seniority is 'senior' → 20."""
    job = _job(title="Senior Python Developer")
    profile = _profile(seniority="senior")
    result = score(job, profile)
    assert result["seniority"] == 20.0


def test_seniority_mismatch_junior_vs_senior():
    """Job is junior, profile wants senior — not adjacent → 0."""
    job = _job(title="Junior Python Developer")
    profile = _profile(seniority="senior")
    result = score(job, profile)
    assert result["seniority"] < 20.0
    assert result["seniority"] == 0.0


def test_seniority_adjacent():
    """Mid and senior are adjacent → 10 pts."""
    job = _job(title="Mid Python Developer")
    profile = _profile(seniority="senior")
    result = score(job, profile)
    assert result["seniority"] == 10.0


def test_seniority_none_profile():
    """Profile seniority is None → seniority component is 0."""
    result = score(_job(), _profile(seniority=None))
    assert result["seniority"] == 0.0


def test_seniority_undetermined_job():
    """Job title has no seniority keyword → neutral (10)."""
    job = _job(title="Python Developer")
    profile = _profile(seniority="senior")
    result = score(job, profile)
    assert result["seniority"] == 10.0


# ---------------------------------------------------------------------------
# Location component
# ---------------------------------------------------------------------------

def test_location_match():
    """Profile location 'Toronto' is in job location → 20."""
    job = _job(location="Toronto, ON")
    profile = _profile(locations=["Toronto"])
    result = score(job, profile)
    assert result["location"] == 20.0


def test_location_no_match_not_remote():
    """Job is not in profile locations and is not remote → 0."""
    job = _job(location="Vancouver, BC")
    profile = _profile(locations=["Toronto"])
    result = score(job, profile)
    assert result["location"] == 0.0


def test_location_remote_with_preference():
    """Job is remote and profile has remote preference → 20."""
    job = _job(location="Remote")
    profile = _profile(locations=["Toronto"], preferences={"remote": True})
    result = score(job, profile)
    assert result["location"] == 20.0


def test_location_remote_without_preference():
    """Job is remote but profile has no remote preference → 0."""
    job = _job(location="Remote")
    profile = _profile(locations=["Toronto"], preferences={})
    result = score(job, profile)
    assert result["location"] == 0.0


def test_location_empty_profile_locations():
    """Profile.locations is empty → neutral (10)."""
    result = score(_job(), _profile(locations=[]))
    assert result["location"] == 10.0


# ---------------------------------------------------------------------------
# Salary component
# ---------------------------------------------------------------------------

def test_salary_overlap():
    """Job [80k–120k] and profile [90k–130k] have significant overlap → 20."""
    job = _job(salary_min=80_000, salary_max=120_000)
    profile = _profile(salary_min=90_000, salary_max=130_000)
    result = score(job, profile)
    assert result["salary"] == 20.0


def test_salary_no_overlap():
    """Job [40k–60k] and profile [90k–130k] have no overlap → 0."""
    job = _job(salary_min=40_000, salary_max=60_000)
    profile = _profile(salary_min=90_000, salary_max=130_000)
    result = score(job, profile)
    assert result["salary"] == 0.0


def test_salary_fully_inside_range():
    """Profile range fully inside job range → significant overlap → 20."""
    job = _job(salary_min=70_000, salary_max=150_000)
    profile = _profile(salary_min=90_000, salary_max=120_000)
    result = score(job, profile)
    assert result["salary"] == 20.0


def test_salary_missing_job_salary():
    """Job has no salary info → neutral (10)."""
    job = _job(salary_min=None, salary_max=None)
    profile = _profile(salary_min=90_000, salary_max=130_000)
    result = score(job, profile)
    assert result["salary"] == 10.0


def test_salary_missing_profile_salary():
    """Profile has no salary info → neutral (10)."""
    job = _job(salary_min=80_000, salary_max=120_000)
    profile = _profile(salary_min=None, salary_max=None)
    result = score(job, profile)
    assert result["salary"] == 10.0


def test_salary_both_missing():
    """Both sides have no salary info → neutral (10)."""
    job = _job(salary_min=None, salary_max=None)
    profile = _profile(salary_min=None, salary_max=None)
    result = score(job, profile)
    assert result["salary"] == 10.0


# ---------------------------------------------------------------------------
# Composite score
# ---------------------------------------------------------------------------

def test_composite_is_sum_of_components():
    """score['score'] must equal the sum of the four components."""
    result = score(_job(), _profile())
    expected = result["skills"] + result["seniority"] + result["location"] + result["salary"]
    assert abs(result["score"] - expected) < 1e-9


def test_composite_between_0_and_100():
    """Composite score is always in [0, 100]."""
    result = score(_job(), _profile())
    assert 0.0 <= result["score"] <= 100.0


def test_perfect_match_near_100():
    """A profile that matches on all dimensions should score close to 100."""
    job = _job(
        title="Senior Python Django Engineer",
        description="Expert in Python, Django, and PostgreSQL required.",
        location="Toronto, ON",
        salary_min=90_000,
        salary_max=130_000,
    )
    profile = _profile(
        skills=["Python", "Django", "PostgreSQL"],
        seniority="senior",
        locations=["Toronto"],
        salary_min=90_000,
        salary_max=130_000,
    )
    result = score(job, profile)
    assert result["score"] >= 90.0


def test_zero_match_scores_low():
    """A profile with no overlap at all should score 0 or near 0."""
    job = _job(
        title="Junior Java Developer",
        description="Spring Boot and Kafka experience required.",
        location="Vancouver, BC",
        salary_min=40_000,
        salary_max=55_000,
    )
    profile = _profile(
        skills=["Python", "Django", "PostgreSQL"],
        seniority="senior",
        locations=["Toronto"],
        salary_min=90_000,
        salary_max=130_000,
        preferences={},
    )
    result = score(job, profile)
    # skills=0, seniority=0 (junior vs senior not adjacent), location=0, salary=0
    assert result["score"] == 0.0
