"""Pass 2 OpenAI re-ranking engine.

Takes the top Pass 1 scored jobs plus the user profile, calls the OpenAI
chat completions API to produce a numeric LLM score and a short human-readable
rationale per job, and returns the enriched results.

API failures are caught and handled gracefully — affected jobs are included
in the output with ``llm_score=None`` and ``llm_rationale=None``.  No
exception propagates to the caller.

This module is free of database I/O — it is a pure transformation with one
external call (OpenAI).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from openai import OpenAI

from app.models import Profile
from app.settings import settings
from app.sources.normalize import Job

logger = logging.getLogger(__name__)

_MODEL = "gpt-4o-mini"

_SYSTEM_PROMPT = (
    "You are a job-matching assistant. "
    "Given a job posting and a candidate profile, evaluate how well the job "
    "matches the candidate. "
    "Respond with a JSON object with exactly two keys: "
    '"score" (integer 0-100) and "rationale" (one concise sentence). '
    "Do not include any other text."
)


@dataclass
class RankedJob:
    """A job enriched with Pass 2 LLM scores.

    Attributes:
        job:            The canonical Job dataclass instance.
        pass1_score:    The composite score produced by Pass 1 (0–100).
        llm_score:      The LLM-assigned score (0–100), or ``None`` if the
                        OpenAI call failed.
        llm_rationale:  A short human-readable rationale, or ``None`` if the
                        OpenAI call failed.
    """

    job: Job
    pass1_score: float
    llm_score: float | None
    llm_rationale: str | None


@dataclass
class RerankResult:
    """Result returned by :func:`rerank`, including token usage.

    Attributes:
        jobs:       Re-ranked job list (one per input job, up to ``cap``).
        tokens_in:  Total ``prompt_tokens`` consumed across all OpenAI calls.
        tokens_out: Total ``completion_tokens`` produced across all OpenAI calls.
    """

    jobs: list[RankedJob]
    tokens_in: int
    tokens_out: int


def _build_user_message(job: Job, profile: Profile) -> str:
    """Render the user-turn prompt from a job and profile."""
    skills_str = ", ".join(profile.skills) if profile.skills else "not specified"
    seniority_str = profile.seniority or "not specified"
    locations_str = ", ".join(profile.locations) if profile.locations else "not specified"

    return (
        f"Job title: {job.title or 'Unknown'}\n"
        f"Company: {job.company or 'Unknown'}\n"
        f"Location: {job.location or 'Unknown'}\n"
        f"Description: {(job.description or '')[:800]}\n"
        f"\n"
        f"Candidate profile:\n"
        f"  Skills: {skills_str}\n"
        f"  Seniority: {seniority_str}\n"
        f"  Preferred locations: {locations_str}\n"
        f"\n"
        f"Score this job for the candidate and provide a rationale."
    )


def rerank(
    scored_jobs: list[tuple[Job, dict[str, float]]],
    profile: Profile,
    *,
    cap: int = 20,
) -> RerankResult:
    """Re-rank the top Pass 1 jobs using the OpenAI chat completions API.

    Args:
        scored_jobs: A list of ``(Job, score_dict)`` pairs as returned by
                     ``pass1.score()``.  The list may contain any number of
                     entries — this function caps it at ``cap`` internally.
        profile:     The user's ``Profile`` instance.
        cap:         Maximum number of jobs to send to OpenAI.  Defaults to
                     20 (cost-control invariant from architecture spec).

    Returns:
        A :class:`RerankResult` containing the ranked jobs list (one per input
        job, up to ``cap``), sorted by Pass 1 score descending, plus
        accumulated ``tokens_in`` and ``tokens_out`` from all OpenAI calls.
        Jobs whose OpenAI call failed will have ``llm_score=None`` and
        ``llm_rationale=None``; their token contribution is 0.
    """
    if not scored_jobs:
        return RerankResult(jobs=[], tokens_in=0, tokens_out=0)

    # Enforce cap — sort by pass1 score and take the best `cap` jobs.
    top = sorted(scored_jobs, key=lambda x: x[1]["score"], reverse=True)[:cap]

    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    results: list[RankedJob] = []
    total_tokens_in = 0
    total_tokens_out = 0

    for job, score_dict in top:
        pass1_score = score_dict["score"]
        try:
            user_message = _build_user_message(job, profile)
            response = client.chat.completions.create(
                model=_MODEL,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.0,
                max_tokens=256,
            )
            # Accumulate token usage from this call.
            if response.usage is not None:
                total_tokens_in += response.usage.prompt_tokens
                total_tokens_out += response.usage.completion_tokens
            content = response.choices[0].message.content or ""
            parsed = json.loads(content)
            llm_score = float(parsed["score"])
            llm_rationale = str(parsed["rationale"])
            results.append(
                RankedJob(
                    job=job,
                    pass1_score=pass1_score,
                    llm_score=llm_score,
                    llm_rationale=llm_rationale,
                )
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "OpenAI re-ranking failed for job %r (%s): %s",
                job.external_id,
                job.title,
                exc,
            )
            results.append(
                RankedJob(
                    job=job,
                    pass1_score=pass1_score,
                    llm_score=None,
                    llm_rationale=None,
                )
            )

    return RerankResult(jobs=results, tokens_in=total_tokens_in, tokens_out=total_tokens_out)
