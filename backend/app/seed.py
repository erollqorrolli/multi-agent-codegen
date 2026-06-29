"""Populate the database with realistic demo data — no LLM calls.

Lets you run the dashboard and see runs, agent steps, sandbox results, and
learned lessons without a Gemini key. Safe to run repeatedly (it clears first).

    export DATABASE_URL="sqlite+aiosqlite:///./demo.db"
    python -m app.seed
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete

from app.db.models import (
    AgentStep,
    Feedback,
    FeedbackVerdict,
    LearnedLesson,
    PipelineRun,
    RunStatus,
)
from app.db.session import SessionLocal, init_models


def _steps(run_id: str) -> list[AgentStep]:
    base = [
        ("architect", "gemini-2.5-pro", 3100, 1400, 5200,
         {"tech_stack": ["FastAPI", "PostgreSQL", "SQLAlchemy", "JWT"],
          "api_endpoints": ["POST /auth/register", "POST /auth/login",
                            "POST /expenses", "GET /expenses", "DELETE /expenses/{id}"],
          "rationale": "Conventional, well-supported stack. JWT for stateless auth."}),
        ("implementation", "gemini-2.5-flash", 2800, 4200, 8100,
         {"files": [{"path": "app/main.py"}, {"path": "app/models.py"},
                    {"path": "app/auth.py"}, {"path": "app/routes/expenses.py"}],
          "notes": "Async endpoints, Pydantic validation, password hashing with bcrypt."}),
        ("test", "gemini-2.5-flash", 3900, 2600, 6400,
         {"files": [{"path": "tests/test_auth.py"}, {"path": "tests/test_expenses.py"}],
          "validated": True, "coverage_notes": "Auth flow, CRUD, and permission checks."}),
        ("security", "gemini-2.5-pro", 4100, 900, 4800,
         {"passed": True, "findings": []}),
        ("optimization", "gemini-2.5-flash", 3700, 700, 3100,
         {"suggestions": [{"area": "database", "issue": "List endpoint not paginated",
                           "improvement": "Add limit/offset pagination",
                           "estimated_impact": "Avoids large payloads at scale"}]}),
        ("sandbox", "local", None, None, 2400,
         {"ran": True, "passed": True, "framework": "pytest", "total": 9,
          "passed_count": 9, "failed_count": 0, "backend": "local",
          "summary": "9 passed, 0 failed, 0 error, 0 skipped"}),
    ]
    return [
        AgentStep(
            run_id=run_id, sequence=i + 1, agent=name, model=model,
            input_tokens=inp, output_tokens=out, duration_ms=dur, output=output,
        )
        for i, (name, model, inp, out, dur, output) in enumerate(base)
    ]


async def main() -> None:
    await init_models()
    async with SessionLocal() as session:
        # Clean slate.
        for model in (Feedback, AgentStep, LearnedLesson, PipelineRun):
            await session.execute(delete(model))
        await session.commit()

        now = datetime.now(timezone.utc)

        run1 = PipelineRun(
            repo="erollqorrolli/demo-expenses",
            issue_number=12,
            issue_title="Build a REST API for expense tracking with auth",
            issue_body="Users can register, log in, and CRUD their own expenses.",
            status=RunStatus.SUCCEEDED,
            pr_url="https://github.com/erollqorrolli/demo-expenses/pull/13",
            generated_files={"app/main.py": "...", "app/auth.py": "...",
                             "tests/test_expenses.py": "..."},
            total_input_tokens=21300,
            total_output_tokens=10800,
            completed_at=now - timedelta(minutes=4),
        )
        run1.steps = _steps("placeholder")
        session.add(run1)
        await session.flush()
        for s in run1.steps:
            s.run_id = run1.id

        run2 = PipelineRun(
            repo="erollqorrolli/demo-expenses",
            issue_number=21,
            issue_title="Add CSV export endpoint for expenses",
            issue_body="GET /expenses/export returns a CSV of the user's expenses.",
            status=RunStatus.RUNNING,
            total_input_tokens=6200,
            total_output_tokens=2100,
        )
        session.add(run2)

        lessons = [
            LearnedLesson(agent="security", lesson="Always rate-limit auth endpoints "
                          "to slow down credential stuffing.", weight=2.3, times_applied=3),
            LearnedLesson(agent="implementation", lesson="Paginate list endpoints by "
                          "default; never return unbounded result sets.", weight=1.8,
                          times_applied=2),
            LearnedLesson(agent="architect", lesson="Prefer UUID primary keys for "
                          "resources exposed in public URLs.", weight=1.5, times_applied=1),
        ]
        session.add_all(lessons)
        await session.flush()

        session.add(Feedback(run_id=run1.id, verdict=FeedbackVerdict.ACCEPTED,
                             comment="Clean and well-tested. Merged."))
        await session.commit()

    print("Seeded 2 runs, 6 agent steps, 3 learned lessons, 1 feedback.")


if __name__ == "__main__":
    asyncio.run(main())
