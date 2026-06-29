"""Orchestrator — coordinates the five agents into one pipeline run.

Coordination model:

    architect ──> implementation ──┬─> test
                       ▲           ├─> security
                       │           └─> optimization
                       │                   │
                       └──── fix loop ◄─────┘   (if security fails / tests invalid)

  * architect → implementation is a hard dependency (run in order);
  * test / security / optimization only depend on the implementation, so they
    fan out concurrently (asyncio.gather);
  * if the Security agent reports high/critical findings (or tests judge the
    implementation invalid), the orchestrator feeds those back to the
    Implementation agent and re-runs the review — up to `max_iterations`.

Every agent step is persisted (AgentStep) so the dashboard can replay a run.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.architect import ArchitectAgent
from app.agents.base import BaseAgent
from app.agents.context import PipelineContext
from app.agents.implementation import ImplementationAgent
from app.agents.optimization import OptimizationAgent
from app.agents.security import SecurityAgent
from app.agents.test_agent import TestAgent
from app.config import get_settings
from app.db.models import AgentStep, PipelineRun, RunStatus
from app.llm.base import LLMProvider
from app.sandbox import get_sandbox
from app.sandbox.base import SandboxResult
from app.schemas.pipeline import GenerationRequest, PipelineResult
from app.services.learning import load_lessons
from app.services.pr_builder import build_pr_body

logger = logging.getLogger(__name__)


class Orchestrator:
    def __init__(
        self,
        provider: LLMProvider,
        session: AsyncSession,
        *,
        max_iterations: int = 2,
    ) -> None:
        self._session = session
        self._max_iterations = max_iterations

        self.architect = ArchitectAgent(provider)
        self.implementation = ImplementationAgent(provider)
        self.test = TestAgent(provider)
        self.security = SecurityAgent(provider)
        self.optimization = OptimizationAgent(provider)

        self._seq = 0
        # Steps tracked locally; we never read the lazy `run.steps` relationship
        # in this async context (that would trigger sync IO -> MissingGreenlet).
        self._steps: list[AgentStep] = []

    async def run(self, request: GenerationRequest) -> PipelineResult:
        run = PipelineRun(
            repo=request.repo,
            issue_number=request.issue_number,
            issue_title=request.issue_title,
            issue_body=request.issue_body,
            status=RunStatus.RUNNING,
        )
        self._session.add(run)
        await self._session.commit()
        await self._session.refresh(run)

        try:
            result = await self._execute(run, request)
            run.status = RunStatus.SUCCEEDED
            run.generated_files = {
                f.path: f.content
                for f in [*result.implementation.files, *result.tests.files]
            }
            run.completed_at = datetime.now(timezone.utc)
            await self._session.commit()
            return result
        except Exception as exc:  # noqa: BLE001 — record and re-raise
            logger.exception("Pipeline run %s failed", run.id)
            run.status = RunStatus.FAILED
            run.error = str(exc)
            run.completed_at = datetime.now(timezone.utc)
            await self._session.commit()
            raise

    # --- internals ------------------------------------------------------------
    async def _execute(self, run: PipelineRun, request: GenerationRequest) -> PipelineResult:
        ctx = PipelineContext(request=request, lessons=await load_lessons(self._session))

        # 1) Architecture (smart tier, hard dependency for everything else).
        ctx.architecture = await self._step(run, self.architect, ctx)

        # 2) Implementation.
        ctx.implementation = await self._step(run, self.implementation, ctx)

        # 3) Review fan-out + fix loop.
        for iteration in range(self._max_iterations):
            tests, security, optimization = await asyncio.gather(
                self._step(run, self.test, ctx),
                self._step(run, self.security, ctx),
                self._step(run, self.optimization, ctx),
            )
            ctx.tests, ctx.security, ctx.optimization = tests, security, optimization

            # Actually execute the generated tests — real signal, not self-report.
            ctx.test_execution = await self._run_sandbox(run, ctx)
            tests_ok = ctx.test_execution.passed if ctx.test_execution else tests.validated

            if security.passed and tests_ok:
                break  # converged
            if iteration == self._max_iterations - 1:
                break  # out of budget; ship with findings noted in the PR

            logger.info("Run %s: re-implementing to resolve findings (iter %d)", run.id, iteration)
            ctx.implementation = await self._step(
                run, self.implementation, ctx, extra=self._fix_brief(ctx)
            )

        run.total_input_tokens = sum(s.input_tokens or 0 for s in self._steps)
        run.total_output_tokens = sum(s.output_tokens or 0 for s in self._steps)

        result = PipelineResult(
            run_id=run.id,
            architecture=ctx.architecture,
            implementation=ctx.implementation,
            tests=ctx.tests,
            security=ctx.security,
            optimization=ctx.optimization,
            test_execution=ctx.test_execution.to_dict() if ctx.test_execution else None,
        )
        result.pr_body = build_pr_body(request, result)
        return result

    async def _run_sandbox(self, run: PipelineRun, ctx: PipelineContext) -> SandboxResult | None:
        """Execute the generated tests against the implementation, persist a step."""
        settings = get_settings()
        if not settings.sandbox_enabled or ctx.implementation is None or ctx.tests is None:
            return None

        files = [*ctx.implementation.files, *ctx.tests.files]
        start = time.perf_counter()
        result = await get_sandbox().run(files)

        self._seq += 1
        step = AgentStep(
            run_id=run.id,
            sequence=self._seq,
            agent="sandbox",
            model=result.backend,
            output=result.to_dict(),
            duration_ms=int((time.perf_counter() - start) * 1000),
        )
        self._session.add(step)
        self._steps.append(step)
        await self._session.commit()
        logger.info("Run %s sandbox(%s): %s", run.id, result.backend, result.summary)
        return result

    async def _step(
        self,
        run: PipelineRun,
        agent: BaseAgent,
        ctx: PipelineContext,
        *,
        extra: str | None = None,
    ):
        """Run one agent, persist an AgentStep, return its typed output."""
        start = time.perf_counter()
        if extra:
            # Temporarily augment the agent's task with the fix brief.
            original = agent.build_task
            agent.build_task = lambda c, _o=original, _e=extra: _o(c) + "\n\n" + _e  # type: ignore
        try:
            output = await agent.run(ctx)
        finally:
            if extra:
                agent.build_task = original  # type: ignore

        self._seq += 1
        resp = agent.last_response
        step = AgentStep(
            run_id=run.id,
            sequence=self._seq,
            agent=agent.name,
            model=resp.model if resp else None,
            output=output.model_dump(),
            input_tokens=resp.input_tokens if resp else None,
            output_tokens=resp.output_tokens if resp else None,
            duration_ms=int((time.perf_counter() - start) * 1000),
        )
        self._session.add(step)
        self._steps.append(step)
        await self._session.commit()
        return output

    @staticmethod
    def _fix_brief(ctx: PipelineContext) -> str:
        """Compose a feedback brief from the latest review for the next impl pass."""
        lines = ["REVISION REQUIRED — address the following and re-emit the full file set:"]
        if ctx.security and not ctx.security.passed:
            for f in ctx.security.findings:
                if f.severity in ("critical", "high"):
                    lines.append(f"- [SECURITY/{f.severity}] {f.issue} @ {f.location} → {f.fix}")
        # Prefer the *real* test run over the agent's self-assessment.
        ex = ctx.test_execution
        if ex and ex.ran and not ex.passed:
            lines.append(f"- [TESTS FAILED] {ex.summary}. Fix the code so these pass:")
            lines.append(f"```\n{ex.output}\n```")
        elif ctx.tests and not ctx.tests.validated:
            lines.append(f"- [TESTS] Implementation judged incomplete: {ctx.tests.coverage_notes}")
        return "\n".join(lines)
