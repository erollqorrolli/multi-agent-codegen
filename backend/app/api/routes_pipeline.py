"""Pipeline + dashboard API.

Lets you trigger a generation locally (no GitHub needed), inspect runs/steps for
the dashboard, and submit accept/reject feedback that feeds the learning loop.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agents.orchestrator import Orchestrator
from app.db.models import FeedbackVerdict, LearnedLesson, PipelineRun
from app.db.session import get_session
from app.llm import QuotaExceededError, get_llm_provider
from app.schemas.pipeline import GenerationRequest, PipelineResult
from app.services.learning import distill_lessons, record_feedback

router = APIRouter(prefix="/api", tags=["pipeline"])


@router.post("/pipeline/generate", response_model=PipelineResult)
async def generate(
    request: GenerationRequest,
    session: AsyncSession = Depends(get_session),
) -> PipelineResult:
    """Run the full 5-agent pipeline synchronously and return the result."""
    orchestrator = Orchestrator(get_llm_provider(), session)
    try:
        return await orchestrator.run(request)
    except QuotaExceededError as exc:
        # 429 so clients can distinguish "out of quota" from a real failure.
        raise HTTPException(429, str(exc)) from exc


@router.get("/runs")
async def list_runs(session: AsyncSession = Depends(get_session)) -> list[dict]:
    rows = (
        await session.execute(select(PipelineRun).order_by(PipelineRun.created_at.desc()))
    ).scalars()
    return [
        {
            "id": r.id,
            "issue_title": r.issue_title,
            "status": r.status,
            "repo": r.repo,
            "pr_url": r.pr_url,
            "total_input_tokens": r.total_input_tokens,
            "total_output_tokens": r.total_output_tokens,
            "created_at": r.created_at,
        }
        for r in rows
    ]


@router.get("/runs/{run_id}")
async def get_run(run_id: str, session: AsyncSession = Depends(get_session)) -> dict:
    # Eager-load steps: accessing the lazy relationship after the await would
    # emit IO outside the async greenlet and raise MissingGreenlet.
    run = (
        await session.execute(
            select(PipelineRun)
            .options(selectinload(PipelineRun.steps))
            .where(PipelineRun.id == run_id)
        )
    ).scalar_one_or_none()
    if run is None:
        raise HTTPException(404, "run not found")
    return {
        "id": run.id,
        "issue_title": run.issue_title,
        "issue_body": run.issue_body,
        "status": run.status,
        "error": run.error,
        "pr_url": run.pr_url,
        "generated_files": run.generated_files,
        "steps": [
            {
                "sequence": s.sequence,
                "agent": s.agent,
                "model": s.model,
                "output": s.output,
                "input_tokens": s.input_tokens,
                "output_tokens": s.output_tokens,
                "duration_ms": s.duration_ms,
            }
            for s in run.steps
        ],
    }


class FeedbackIn(BaseModel):
    verdict: FeedbackVerdict
    comment: str = ""


@router.post("/runs/{run_id}/feedback")
async def submit_feedback(
    run_id: str,
    body: FeedbackIn,
    session: AsyncSession = Depends(get_session),
) -> dict:
    run = await session.get(PipelineRun, run_id)
    if run is None:
        raise HTTPException(404, "run not found")
    fb = await record_feedback(
        session, run_id=run_id, verdict=body.verdict, comment=body.comment
    )
    lessons = await distill_lessons(session, get_llm_provider(), feedback=fb)
    return {
        "feedback_id": fb.id,
        "lessons_learned": [{"agent": ls.agent, "lesson": ls.lesson} for ls in lessons],
    }


@router.get("/lessons")
async def list_lessons(session: AsyncSession = Depends(get_session)) -> list[dict]:
    rows = (
        await session.execute(select(LearnedLesson).order_by(LearnedLesson.weight.desc()))
    ).scalars()
    return [
        {
            "agent": ls.agent,
            "lesson": ls.lesson,
            "weight": ls.weight,
            "times_applied": ls.times_applied,
        }
        for ls in rows
    ]
