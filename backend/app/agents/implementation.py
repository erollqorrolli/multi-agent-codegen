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
            "  - INTERNAL CONSISTENCY IS CRITICAL: every symbol you import in one file "
            "must actually be defined in the file it's imported from. Keep class, function, "
            "and schema names identical across modules. The project must import cleanly.\n"
            "Keep the project FOCUSED: only the files needed to run and test the feature. "
            "Skip CI configs, Dockerfiles, license files, and editor configs unless asked."
        )

    def build_task(self, ctx: PipelineContext) -> str:
        arch = ctx.architecture
        assert arch is not None, "Implementation requires architecture context"
        spec = (
            "ARCHITECTURE TO IMPLEMENT\n"
            f"Tech stack: {', '.join(arch.tech_stack)}\n"
            f"Data models:\n{arch.data_models}\n"
            "API endpoints:\n" + "\n".join(f"  - {e}" for e in arch.api_endpoints) + "\n"
            f"Components: {', '.join(arch.components)}\n\n"
        )

        # Revision pass: the previous file set is still in context. Show it so the
        # agent repairs the actual code instead of regenerating blindly (which
        # tends to reintroduce cross-file inconsistencies).
        if ctx.implementation is not None:
            current = "\n\n".join(
                f"### {f.path}\n```{f.language}\n{f.content}\n```"
                for f in ctx.implementation.files
            )
            return (
                "You are REVISING an existing implementation (full file set below). Apply "
                "the fixes in the revision notes that follow, return the COMPLETE corrected "
                "file set, change only what's necessary, and make sure the project imports "
                f"cleanly.\n\n{spec}CURRENT FILES:\n{current}\n\n"
                "Produce a JSON object with keys: files (array of {path, content, "
                "language}) — the full corrected set — and notes (string)."
            )

        return spec + (
            "Produce a JSON object with keys: files (array of {path, content, language}) "
            "containing every source file needed to run the system, and notes (string) "
            "describing anything the reviewer should know."
        )
