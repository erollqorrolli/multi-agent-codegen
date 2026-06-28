"""The mutable context object threaded through the pipeline.

Each agent reads what prior agents produced and writes its own result. This is
the concrete mechanism behind "agents pass context and iterate".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.sandbox.base import SandboxResult

from app.schemas.pipeline import (
    ArchitectOutput,
    GenerationRequest,
    ImplementationOutput,
    OptimizationOutput,
    SecurityOutput,
    TestOutput,
)


@dataclass
class PipelineContext:
    request: GenerationRequest
    # Distilled lessons from past feedback, keyed by agent name.
    lessons: dict[str, list[str]] = field(default_factory=dict)

    architecture: ArchitectOutput | None = None
    implementation: ImplementationOutput | None = None
    tests: TestOutput | None = None
    security: SecurityOutput | None = None
    optimization: OptimizationOutput | None = None
    # Real result of executing the generated tests in a sandbox.
    test_execution: "SandboxResult | None" = None

    def lessons_for(self, agent: str) -> list[str]:
        return self.lessons.get(agent, [])
