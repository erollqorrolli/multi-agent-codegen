"""End-to-end pipeline tests with no API key, network, or quota.

Drives the real Orchestrator (and the real local sandbox) with a stub LLM,
proving the agents coordinate, the fix loop repairs failing code, steps persist,
and the learning loop distills feedback. These exercise the exact code paths that
broke on the first live run (greenlet, fix loop), so they're real regression guards.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.agents.orchestrator import Orchestrator
from app.db.models import AgentStep, Base, FeedbackVerdict, PipelineRun, RunStatus
from app.schemas.pipeline import GenerationRequest
from app.services.learning import distill_lessons, load_lessons, record_feedback
from tests.stubs import StubProvider


@pytest.fixture
async def session():
    # StaticPool keeps one shared in-memory SQLite connection for the whole test.
    engine = create_async_engine(
        "sqlite+aiosqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        yield s
    await engine.dispose()


async def test_pipeline_happy_path(session):
    orch = Orchestrator(StubProvider(), session, max_iterations=2)
    result = await orch.run(GenerationRequest(issue_title="Add two numbers"))

    # All five agents produced structured output.
    assert result.architecture.tech_stack == ["Python", "FastAPI"]
    assert result.implementation.files
    assert result.security.passed is True
    assert result.optimization.suggestions

    # The sandbox actually executed the generated tests and they passed.
    assert result.test_execution is not None
    assert result.test_execution["ran"] is True
    assert result.test_execution["passed"] is True

    # Steps were persisted: architect, implementation, test, security, optimization, sandbox.
    run = await session.get(PipelineRun, result.run_id)
    assert run.status == RunStatus.SUCCEEDED
    assert run.total_input_tokens > 0
    assert "Python" in result.pr_body

    steps = (
        await session.execute(
            select(AgentStep).where(AgentStep.run_id == result.run_id).order_by(AgentStep.sequence)
        )
    ).scalars().all()
    assert [s.agent for s in steps] == [
        "architect", "implementation", "test", "security", "optimization", "sandbox"
    ]


async def test_fix_loop_repairs_failing_code(session):
    # First implementation is buggy -> sandbox fails -> loop revises -> passes.
    orch = Orchestrator(StubProvider(buggy_first=True), session, max_iterations=2)
    result = await orch.run(GenerationRequest(issue_title="Add two numbers"))

    assert result.test_execution["passed"] is True  # converged after a fix

    steps = (
        await session.execute(select(AgentStep).where(AgentStep.run_id == result.run_id))
    ).scalars().all()
    impl_steps = [s for s in steps if s.agent == "implementation"]
    sandbox_steps = [s for s in steps if s.agent == "sandbox"]
    assert len(impl_steps) == 2  # initial + one revision
    assert len(sandbox_steps) == 2  # failed then passed


async def test_learning_loop_distills_feedback(session):
    run = PipelineRun(issue_title="Add auth", status=RunStatus.SUCCEEDED)
    session.add(run)
    await session.commit()
    await session.refresh(run)

    fb = await record_feedback(
        session, run_id=run.id, verdict=FeedbackVerdict.REJECTED, comment="No rate limiting on login"
    )
    lessons = await distill_lessons(session, StubProvider(), feedback=fb)
    assert lessons and lessons[0].agent == "security"

    loaded = await load_lessons(session)
    assert "security" in loaded
    assert any("rate-limit" in t.lower() for t in loaded["security"])
