"""Implementation Agent — turns the architecture into real source files."""

from __future__ import annotations

from app.agents.base import BaseAgent
from app.agents.context import PipelineContext
from app.llm.base import ModelTier
from app.schemas.pipeline import ImplementationOutput


class ImplementationAgent(BaseAgent[ImplementationOutput]):
    name = "implementation"
    tier = ModelTier.FAST
    output_model = ImplementationOutput

    def system_prompt(self) -> str:
        return (
            "You are a Senior Python Backend Engineer. Implement the architecture as a "
            "complete, runnable FastAPI project in Python 3.12 (async FastAPI, SQLAlchemy "
            "2.0 async, Pydantic v2). Write idiomatic, production-quality code with error "
            "handling and input validation. Hard requirements so the result is testable:\n"
            "  - Use a package layout rooted at `app/` (include `app/__init__.py`); tests "
            "import from `app...`.\n"
            "  - Include a `requirements.txt` listing EVERY dependency (fastapi, uvicorn, "
            "sqlalchemy, pydantic, pydantic-settings, aiosqlite, httpx, pytest, "
            "pytest-asyncio, passlib[bcrypt], pyjwt, etc.).\n"
            "  - The app must read DATABASE_URL from the environment and DEFAULT to "
            "`sqlite+aiosqlite:///./app.db` so it runs with no external database.\n"
            "  - No TODOs or placeholder bodies — write the real implementation.\n"
            "Keep the project FOCUSED: only the files needed to run and test the feature. "
            "Skip CI configs, Dockerfiles, license files, and editor configs unless asked."
        )

    def build_task(self, ctx: PipelineContext) -> str:
        arch = ctx.architecture
        assert arch is not None, "Implementation requires architecture context"
        return (
            "ARCHITECTURE TO IMPLEMENT\n"
            f"Tech stack: {', '.join(arch.tech_stack)}\n"
            f"Data models:\n{arch.data_models}\n"
            f"API endpoints:\n" + "\n".join(f"  - {e}" for e in arch.api_endpoints) + "\n"
            f"Components: {', '.join(arch.components)}\n\n"
            "Produce a JSON object with keys: files (array of {path, content, language}) "
            "containing every source file needed to run the system, and notes (string) "
            "describing anything the reviewer should know."
        )
