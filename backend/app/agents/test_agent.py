"""Test Agent — writes comprehensive tests against the generated implementation."""

from __future__ import annotations

from app.agents.base import BaseAgent
from app.agents.context import PipelineContext
from app.llm.base import ModelTier
from app.schemas.pipeline import TestOutput


class TestAgent(BaseAgent[TestOutput]):
    name = "test"
    tier = ModelTier.FAST
    output_model = TestOutput

    def system_prompt(self) -> str:
        return (
            "You are a Senior QA / Test Engineer. Write thorough pytest tests: happy paths, "
            "edge cases, auth/permission checks, and failure modes. Hard requirements so "
            "the tests actually run in a clean sandbox with no external services:\n"
            "  - Use pytest; put tests under `tests/` importing from `app...`.\n"
            "  - Drive the API with FastAPI's TestClient or httpx ASGI transport.\n"
            "  - Use an in-memory or temp-file SQLite database (override DATABASE_URL / the "
            "DB dependency) — never require a running Postgres, Redis, or network.\n"
            "  - Tests must pass against the provided implementation as-is."
        )

    def build_task(self, ctx: PipelineContext) -> str:
        impl = ctx.implementation
        assert impl is not None, "Test agent requires implementation context"
        file_list = "\n".join(f"  - {f.path} ({f.language})" for f in impl.files)
        # Include the actual code so tests target real signatures, not guesses.
        bodies = "\n\n".join(
            f"### {f.path}\n```{f.language}\n{f.content}\n```" for f in impl.files
        )
        return (
            f"IMPLEMENTED FILES:\n{file_list}\n\nSOURCE:\n{bodies}\n\n"
            "Produce a JSON object with keys: files (array of {path, content, language}) "
            "containing test files, coverage_notes (string), and validated (boolean: your "
            "best assessment of whether the implementation satisfies the request)."
        )
