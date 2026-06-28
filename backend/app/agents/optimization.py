"""Optimization Agent — profiles the code (statically) and suggests improvements."""

from __future__ import annotations

from app.agents.base import BaseAgent
from app.agents.context import PipelineContext
from app.llm.base import ModelTier
from app.schemas.pipeline import OptimizationOutput


class OptimizationAgent(BaseAgent[OptimizationOutput]):
    name = "optimization"
    tier = ModelTier.FAST
    output_model = OptimizationOutput

    def system_prompt(self) -> str:
        return (
            "You are a Performance Engineer. Review the implementation for performance and "
            "efficiency problems: N+1 queries, missing indexes, unnecessary allocations, "
            "blocking I/O on the hot path, missing caching/pagination, and algorithmic "
            "inefficiencies. Suggest concrete, high-impact improvements. Do not invent "
            "problems — if the code is already efficient, return few or no suggestions."
        )

    def build_task(self, ctx: PipelineContext) -> str:
        impl = ctx.implementation
        assert impl is not None, "Optimization agent requires implementation context"
        bodies = "\n\n".join(
            f"### {f.path}\n```{f.language}\n{f.content}\n```" for f in impl.files
        )
        arch = ctx.architecture
        db_hint = f"\nData model:\n{arch.data_models}" if arch else ""
        return (
            f"CODE TO PROFILE:{db_hint}\n\n{bodies}\n\n"
            "Produce a JSON object with key: suggestions (array of {area, issue, "
            "improvement, estimated_impact})."
        )
