"""Tests for backend/app/scoring/pass2.py.

All OpenAI calls are mocked — no live network traffic in these tests.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from app.models import Profile
from app.scoring.pass2 import RankedJob, rerank
from app.sources.normalize import Job

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _job(external_id: str = "1", title: str = "Software Engineer") -> Job:
    return Job(
        source="adzuna",
        external_id=external_id,
        title=title,
        company="Acme Corp",
        location="Toronto, ON",
        salary_min=90_000,
        salary_max=120_000,
        description=f"A great job for {title}.",
        url=f"https://example.com/job/{external_id}",
    )


def _profile() -> Profile:
    return Profile(
        target_titles=["Software Engineer"],
        skills=["Python", "Django"],
        seniority="senior",
        locations=["Toronto"],
        salary_min=85_000,
        salary_max=130_000,
        preferences={},
    )


def _score_dict(score: float = 75.0) -> dict[str, float]:
    return {
        "score": score,
        "skills": 30.0,
        "seniority": 20.0,
        "location": 15.0,
        "salary": score - 65.0,
    }


def _make_mock_response(score: int = 85, rationale: str = "Good skills match") -> MagicMock:
    """Build a mock object that mimics the openai ChatCompletion response shape."""
    mock_response = MagicMock()
    mock_response.choices[0].message.content = json.dumps(
        {"score": score, "rationale": rationale}
    )
    return mock_response


# ---------------------------------------------------------------------------
# Empty input
# ---------------------------------------------------------------------------

def test_empty_input_returns_empty_list():
    """rerank() with no jobs should return [] immediately without calling OpenAI."""
    with patch("app.scoring.pass2.OpenAI") as mock_openai_cls:
        result = rerank([], _profile())

    assert result == []
    mock_openai_cls.assert_not_called()


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_happy_path_single_job():
    """Single job: mock returns valid JSON → RankedJob has correct llm fields."""
    job = _job("42", "Senior Python Developer")
    scored_jobs = [(job, _score_dict(80.0))]

    with patch("app.scoring.pass2.OpenAI") as mock_openai_cls:
        mock_client = mock_openai_cls.return_value
        mock_client.chat.completions.create.return_value = _make_mock_response(
            score=85, rationale="Good skills match"
        )

        results = rerank(scored_jobs, _profile())

    assert len(results) == 1
    ranked = results[0]
    assert isinstance(ranked, RankedJob)
    assert ranked.job is job
    assert ranked.pass1_score == 80.0
    assert ranked.llm_score == 85.0
    assert ranked.llm_rationale == "Good skills match"


def test_happy_path_multiple_jobs():
    """Multiple jobs: each gets its own llm_score and llm_rationale."""
    jobs_and_scores = [
        (_job("1", "Backend Engineer"), _score_dict(70.0)),
        (_job("2", "Python Developer"), _score_dict(60.0)),
    ]
    responses = [
        _make_mock_response(score=72, rationale="Solid backend skills"),
        _make_mock_response(score=65, rationale="Python experience matches"),
    ]

    with patch("app.scoring.pass2.OpenAI") as mock_openai_cls:
        mock_client = mock_openai_cls.return_value
        mock_client.chat.completions.create.side_effect = responses

        results = rerank(jobs_and_scores, _profile())

    assert len(results) == 2
    assert results[0].llm_score == 72.0
    assert results[0].llm_rationale == "Solid backend skills"
    assert results[1].llm_score == 65.0
    assert results[1].llm_rationale == "Python experience matches"


# ---------------------------------------------------------------------------
# Cap enforcement
# ---------------------------------------------------------------------------

def test_cap_enforcement_default_20():
    """25 input jobs → only the top 20 by pass1 score are sent to OpenAI."""
    # Build 25 jobs with different scores so sorting is deterministic
    scored_jobs = [
        (_job(str(i), f"Job {i}"), _score_dict(float(i)))
        for i in range(1, 26)  # scores 1..25; top 20 are IDs 6..25
    ]

    call_count = 0

    def mock_create(**kwargs):
        nonlocal call_count
        call_count += 1
        return _make_mock_response(score=80, rationale="OK")

    with patch("app.scoring.pass2.OpenAI") as mock_openai_cls:
        mock_client = mock_openai_cls.return_value
        mock_client.chat.completions.create.side_effect = mock_create

        results = rerank(scored_jobs, _profile(), cap=20)

    assert len(results) == 20
    assert call_count == 20


def test_cap_enforcement_custom_cap():
    """Custom cap=5 with 10 input jobs → only 5 sent to OpenAI."""
    scored_jobs = [
        (_job(str(i)), _score_dict(float(i)))
        for i in range(1, 11)
    ]

    with patch("app.scoring.pass2.OpenAI") as mock_openai_cls:
        mock_client = mock_openai_cls.return_value
        mock_client.chat.completions.create.return_value = _make_mock_response()

        results = rerank(scored_jobs, _profile(), cap=5)

    assert len(results) == 5
    assert mock_client.chat.completions.create.call_count == 5


def test_cap_selects_top_scorers():
    """Cap should select the highest pass1 scores, not the first N items."""
    # Deliberately put the low-score jobs first in the list
    low_job = _job("low", "Low Score Job")
    high_job = _job("high", "High Score Job")
    scored_jobs = [
        (low_job, _score_dict(10.0)),
        (high_job, _score_dict(90.0)),
    ]

    with patch("app.scoring.pass2.OpenAI") as mock_openai_cls:
        mock_client = mock_openai_cls.return_value
        mock_client.chat.completions.create.return_value = _make_mock_response()

        results = rerank(scored_jobs, _profile(), cap=1)

    assert len(results) == 1
    assert results[0].job is high_job


# ---------------------------------------------------------------------------
# API failure — rate limit error
# ---------------------------------------------------------------------------

def test_rate_limit_error_graceful_fallback():
    """openai.RateLimitError → job included with llm_score=None, no crash."""
    import openai

    job = _job("99", "DevOps Engineer")
    scored_jobs = [(job, _score_dict(55.0))]

    mock_response = MagicMock()
    mock_response.status_code = 429
    rate_limit_error = openai.RateLimitError(
        "rate limit exceeded",
        response=mock_response,
        body=None,
    )

    with patch("app.scoring.pass2.OpenAI") as mock_openai_cls:
        mock_client = mock_openai_cls.return_value
        mock_client.chat.completions.create.side_effect = rate_limit_error

        results = rerank(scored_jobs, _profile())

    assert len(results) == 1
    ranked = results[0]
    assert ranked.job is job
    assert ranked.pass1_score == 55.0
    assert ranked.llm_score is None
    assert ranked.llm_rationale is None


# ---------------------------------------------------------------------------
# API failure — timeout error
# ---------------------------------------------------------------------------

def test_api_timeout_error_graceful_fallback():
    """openai.APITimeoutError → job included with llm_score=None, no crash."""
    import openai

    job = _job("77", "Data Engineer")
    scored_jobs = [(job, _score_dict(62.0))]

    timeout_error = openai.APITimeoutError(request=MagicMock())

    with patch("app.scoring.pass2.OpenAI") as mock_openai_cls:
        mock_client = mock_openai_cls.return_value
        mock_client.chat.completions.create.side_effect = timeout_error

        results = rerank(scored_jobs, _profile())

    assert len(results) == 1
    ranked = results[0]
    assert ranked.job is job
    assert ranked.pass1_score == 62.0
    assert ranked.llm_score is None
    assert ranked.llm_rationale is None


# ---------------------------------------------------------------------------
# API failure — generic / unexpected exception
# ---------------------------------------------------------------------------

def test_generic_exception_graceful_fallback():
    """Any unexpected exception → job included with llm_score=None, no crash."""
    job = _job("55", "ML Engineer")
    scored_jobs = [(job, _score_dict(48.0))]

    with patch("app.scoring.pass2.OpenAI") as mock_openai_cls:
        mock_client = mock_openai_cls.return_value
        mock_client.chat.completions.create.side_effect = RuntimeError(
            "unexpected internal error"
        )

        results = rerank(scored_jobs, _profile())

    assert len(results) == 1
    ranked = results[0]
    assert ranked.llm_score is None
    assert ranked.llm_rationale is None


# ---------------------------------------------------------------------------
# Partial failure — some jobs succeed, some fail
# ---------------------------------------------------------------------------

def test_partial_failure_mixed_results():
    """If one job's API call fails, other jobs still get their scores."""
    job_good = _job("1", "Python Dev")
    job_bad = _job("2", "Java Dev")

    scored_jobs = [
        (job_good, _score_dict(80.0)),
        (job_bad, _score_dict(70.0)),
    ]

    def side_effect(**kwargs):
        # Fail on the second call
        if side_effect.call_count == 0:
            side_effect.call_count += 1
            return _make_mock_response(score=90, rationale="Great Python fit")
        raise RuntimeError("boom")

    side_effect.call_count = 0

    with patch("app.scoring.pass2.OpenAI") as mock_openai_cls:
        mock_client = mock_openai_cls.return_value
        mock_client.chat.completions.create.side_effect = side_effect

        results = rerank(scored_jobs, _profile())

    assert len(results) == 2
    # First job (higher score, processed first) succeeded
    assert results[0].llm_score == 90.0
    assert results[0].llm_rationale == "Great Python fit"
    # Second job failed gracefully
    assert results[1].llm_score is None
    assert results[1].llm_rationale is None


# ---------------------------------------------------------------------------
# JSON parse failure
# ---------------------------------------------------------------------------

def test_malformed_json_response_graceful_fallback():
    """If OpenAI returns non-parseable JSON, job falls back to None fields."""
    job = _job("33", "QA Engineer")
    scored_jobs = [(job, _score_dict(50.0))]

    bad_response = MagicMock()
    bad_response.choices[0].message.content = "This is not JSON at all!"

    with patch("app.scoring.pass2.OpenAI") as mock_openai_cls:
        mock_client = mock_openai_cls.return_value
        mock_client.chat.completions.create.return_value = bad_response

        results = rerank(scored_jobs, _profile())

    assert len(results) == 1
    assert results[0].llm_score is None
    assert results[0].llm_rationale is None
