"""The learning loop.

Two halves:
  * `load_lessons` — pull distilled lessons from the DB and group them by agent,
    so the orchestrator can inject them into prompts (closing the loop on input).
  * `record_feedback` / `distill_lessons` — when a human accepts/rejects a PR,
    turn that signal into durable, agent-scoped guidance for next time.

This is intentionally simple and inspectable (rows you can read), not an opaque
fine-tune — which is exactly what you want to *demo* in a portfolio piece.
"""

from __future__ import annotations

import json
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Feedback, FeedbackVerdict, LearnedLesson, PipelineRun
from app.llm.base import LLMProvider, ModelTier

logger = logging.getLogger(__name__)

# Cap how many lessons we inject per agent so prompts stay focused.
_MAX_LESSONS_PER_AGENT = 5

_VALID_AGENTS = {"architect", "implementation", "test", "security", "optimization"}


async def load_lessons(session: AsyncSession) -> dict[str, list[str]]:
    """Return {agent_name: [lesson, ...]} ordered by weight, capped per agent."""
    rows = (
        await session.execute(
            select(LearnedLesson).order_by(LearnedLesson.weight.desc())
        )
    ).scalars()

    lessons: dict[str, list[str]] = {}
    for row in rows:
        bucket = lessons.setdefault(row.agent, [])
        if len(bucket) < _MAX_LESSONS_PER_AGENT:
            bucket.append(row.lesson)
            row.times_applied += 1
    await session.commit()
    return lessons


async def record_feedback(
    session: AsyncSession,
    *,
    run_id: str,
    verdict: FeedbackVerdict,
    comment: str = "",
    details: dict | None = None,
) -> Feedback:
    fb = Feedback(run_id=run_id, verdict=verdict, comment=comment, details=details or {})
    session.add(fb)
    await session.commit()
    await session.refresh(fb)
    return fb


async def distill_lessons(
    session: AsyncSession,
    provider: LLMProvider,
    *,
    feedback: Feedback,
) -> list[LearnedLesson]:
    """Convert a *negative* signal into agent-scoped lessons via the LLM.

    Acceptances reinforce existing lessons (bump weight); rejections / change
    requests generate new guidance attributed to the responsible agent(s).
    """
    if feedback.verdict == FeedbackVerdict.ACCEPTED:
        # Positive reinforcement: nudge weights of lessons that were applied.
        applied = (
            await session.execute(
                select(LearnedLesson).where(LearnedLesson.times_applied > 0)
            )
        ).scalars()
        for lesson in applied:
            lesson.weight = min(lesson.weight + 0.1, 5.0)
        await session.commit()
        return []

    run = await session.get(PipelineRun, feedback.run_id)
    if run is None:
        return []

    system = (
        "You convert human PR feedback into short, reusable engineering rules for an "
        "automated code-generation pipeline. Each rule is attributed to exactly one of "
        f"these agents: {', '.join(sorted(_VALID_AGENTS))}. Rules must be imperative, "
        "general (not tied to this one PR), and under 20 words.\n"
        "Respond with ONLY JSON: {\"lessons\": [{\"agent\": str, \"lesson\": str}]}"
    )
    task = (
        f"Original request: {run.issue_title}\n\n"
        f"Human verdict: {feedback.verdict}\n"
        f"Human comment:\n{feedback.comment or '(none)'}\n\n"
        "Extract 1-3 lessons that would prevent this feedback next time."
    )
    resp = await provider.generate(prompt=task, system=system, tier=ModelTier.SMART, json_output=True)

    try:
        payload = json.loads(resp.text)
    except json.JSONDecodeError:
        logger.warning("distill_lessons: non-JSON response, skipping")
        return []

    created: list[LearnedLesson] = []
    for item in payload.get("lessons", []):
        agent = str(item.get("agent", "")).strip().lower()
        text = str(item.get("lesson", "")).strip()
        if agent in _VALID_AGENTS and text:
            lesson = LearnedLesson(agent=agent, lesson=text, source_run_id=run.id, weight=1.5)
            session.add(lesson)
            created.append(lesson)
    await session.commit()
    logger.info("distilled %d lesson(s) from feedback %s", len(created), feedback.id)
    return created
