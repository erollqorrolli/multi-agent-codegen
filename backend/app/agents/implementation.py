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
            "You are a Senior Backend Engineer. Implement the architecture you are given "
            "as complete, runnable source files. Write idiomatic, production-quality code "
            "with error handling, input validation, and clear structure. Include "
            "migrations and a minimal deployment/config file where relevant. Do not leave "
            "TODOs or placeholder bodies — write the real implementation."
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
