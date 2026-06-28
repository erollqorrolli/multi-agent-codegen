"""BaseAgent — the shared machinery every specialised agent inherits.

Responsibilities kept here so the concrete agents stay tiny and declarative:
  * assemble the prompt (task + structured upstream context + learned lessons);
  * call the LLM at the right model tier with JSON mode;
  * parse + validate the response into a typed Pydantic model (defensively).
"""

from __future__ import annotations

import json
import logging
import time
from typing import Generic, TypeVar

from pydantic import BaseModel, ValidationError

from app.agents.context import PipelineContext
from app.llm.base import LLMProvider, LLMResponse, ModelTier

logger = logging.getLogger(__name__)

TOut = TypeVar("TOut", bound=BaseModel)


class AgentError(RuntimeError):
    """Raised when an agent cannot produce a valid structured result."""


class BaseAgent(Generic[TOut]):
    #: Stable identifier used in logs, the DB and lesson scoping.
    name: str = "base"
    #: Which model class this agent needs.
    tier: ModelTier = ModelTier.FAST
    #: The Pydantic model the agent must return.
    output_model: type[TOut]

    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider
        # Populated after run() so the orchestrator can persist token usage.
        self.last_response: LLMResponse | None = None
        self.last_duration_ms: int | None = None

    # --- to be implemented by each agent --------------------------------------
    def system_prompt(self) -> str:
        raise NotImplementedError

    def build_task(self, ctx: PipelineContext) -> str:
        """Agent-specific instructions + the upstream context it needs."""
        raise NotImplementedError

    # --- shared run loop ------------------------------------------------------
    async def run(self, ctx: PipelineContext) -> TOut:
        system = self._assemble_system(ctx)
        task = self.build_task(ctx)

        start = time.perf_counter()
        resp = await self._provider.generate(
            prompt=task,
            system=system,
            tier=self.tier,
            json_output=True,
        )
        self.last_duration_ms = int((time.perf_counter() - start) * 1000)
        self.last_response = resp

        return self._parse(resp.text)

    # --- helpers --------------------------------------------------------------
    def _assemble_system(self, ctx: PipelineContext) -> str:
        """Base system prompt + any learned lessons scoped to this agent."""
        system = self.system_prompt().strip()
        lessons = ctx.lessons_for(self.name)
        if lessons:
            bullet = "\n".join(f"- {item}" for item in lessons)
            system += (
                "\n\nLEARNED LESSONS from past human feedback — apply these:\n" + bullet
            )
        system += (
            "\n\nRespond with ONLY a single JSON object matching the required schema. "
            "No markdown fences, no prose outside the JSON."
        )
        return system

    def _parse(self, text: str) -> TOut:
        raw = _extract_json(text)
        try:
            return self.output_model.model_validate(raw)
        except ValidationError as exc:
            logger.warning("%s produced schema-invalid output: %s", self.name, exc)
            raise AgentError(f"{self.name} returned invalid structured output") from exc


def _extract_json(text: str) -> dict:
    """Be forgiving: strip accidental code fences and locate the JSON object."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        text = text.removeprefix("json").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        first, last = text.find("{"), text.rfind("}")
        if first != -1 and last != -1 and last > first:
            return json.loads(text[first : last + 1])
        raise
