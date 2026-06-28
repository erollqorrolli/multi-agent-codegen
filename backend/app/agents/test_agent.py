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
            "You are a Senior QA / Test Engineer. Given an implementation, write thorough "
            "automated tests: happy paths, edge cases, auth/permission checks, and failure "
            "modes. Use the conventional test framework for the stack. Tests must be "
            "concrete and executable against the provided files."
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
