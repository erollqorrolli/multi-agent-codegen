"""Terminal runner — watch the full pipeline without GitHub.

Usage (zero infra — uses a local SQLite file):
    export GEMINI_API_KEY=...                    # from aistudio.google.com/apikey
    export DATABASE_URL=sqlite+aiosqlite:///./demo.db
    python -m app.cli "Build a REST API for expense tracking with auth"

Or against Postgres: run `make db` first and leave DATABASE_URL at its default.
"""

from __future__ import annotations

import asyncio
import sys

from app.agents.orchestrator import Orchestrator
from app.db.session import SessionLocal, init_models
from app.llm import QuotaExceededError, get_llm_provider
from app.schemas.pipeline import GenerationRequest


def _hr(title: str) -> None:
    print(f"\n\033[1m{'─' * 4} {title} {'─' * (60 - len(title))}\033[0m")


async def main(title: str, body: str) -> None:
    await init_models()
    async with SessionLocal() as session:
        orchestrator = Orchestrator(get_llm_provider(), session)
        print(f"\033[1mRequest:\033[0m {title}\nRunning 5-agent pipeline...\n")
        try:
            result = await orchestrator.run(GenerationRequest(issue_title=title, issue_body=body))
        except QuotaExceededError as exc:
            print(f"\033[93m\nQuota:\033[0m {exc}")
            raise SystemExit(2) from exc

    _hr("ARCHITECTURE")
    print("Stack:", ", ".join(result.architecture.tech_stack))
    print("Endpoints:", len(result.architecture.api_endpoints))
    print(result.architecture.rationale)

    _hr(f"IMPLEMENTATION ({len(result.implementation.files)} files)")
    for f in result.implementation.files:
        print(f"  • {f.path} ({f.language}, {len(f.content)} chars)")

    _hr(f"TESTS ({len(result.tests.files)} files)")
    print("Validated:", result.tests.validated)

    _hr("SECURITY")
    print("Passed:", result.security.passed)
    for finding in result.security.findings:
        print(f"  [{finding.severity}] {finding.issue} → {finding.fix}")

    _hr("OPTIMIZATION")
    for s in result.optimization.suggestions:
        print(f"  • {s.area}: {s.improvement} (impact: {s.estimated_impact})")

    _hr("PR BODY")
    print(result.pr_body)
    print(f"\n\033[92mDone.\033[0m Run id: {result.run_id}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Usage: python -m app.cli "<issue title>" "[optional body]"')
        raise SystemExit(1)
    asyncio.run(main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else ""))
