"""Architect Agent — designs the system before any code is written.

Uses the SMART tier (Gemini 2.5 Pro) with a generous thinking budget because
this is the highest-leverage decision in the pipeline: a bad architecture poisons
every downstream agent.
"""

from __future__ import annotations

from app.agents.base import BaseAgent
from app.agents.context import PipelineContext
from app.llm.base import ModelTier
from app.schemas.pipeline import ArchitectOutput


class ArchitectAgent(BaseAgent[ArchitectOutput]):
    name = "architect"
    tier = ModelTier.SMART
    output_model = ArchitectOutput

    def system_prompt(self) -> str:
        return (
            "You are a Principal Software Architect. Design a complete, pragmatic system "
            "using THIS FIXED STACK — do not choose another language or framework:\n"
            "  - Python 3.12, FastAPI (async)\n"
            "  - SQLAlchemy 2.0 (async) for the data layer; Pydantic v2 for schemas\n"
            "  - JWT auth where authentication is needed; bcrypt/passlib for passwords\n"
            "  - pytest for tests, runnable against SQLite (no external services)\n"
            "Define the data model (as SQLAlchemy models or SQL), the API surface, and the "
            "major components. Be concrete and implementable — a junior engineer should be "
            "able to build from your design without further questions."
        )

    def build_task(self, ctx: PipelineContext) -> str:
        r = ctx.request
        return (
            f"FEATURE REQUEST\nTitle: {r.issue_title}\n\nDetails:\n{r.issue_body or '(none)'}\n\n"
            "Produce a JSON object with keys: tech_stack (string[]), data_models (string: "
            "the schema, prefer SQL DDL or clear entity definitions), api_endpoints "
            "(string[]: e.g. 'POST /expenses - create an expense'), components (string[]), "
            "rationale (string: why these choices)."
        )
