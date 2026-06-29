"""Vendor-neutral LLM interface.

The whole point: an agent says "generate with the SMART tier, here's a system
prompt, give me JSON back" and does not care whether that's Gemini, Claude, or
a local model. Concrete providers implement `LLMProvider`.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


class QuotaExceededError(RuntimeError):
    """Raised when the provider's quota is exhausted (e.g. free-tier daily cap).

    Distinct from transient rate limits: retrying within the request won't help,
    so callers should surface a clear message rather than hammering the API.
    """


class ModelTier(enum.StrEnum):
    """Logical model classes. Mapped to concrete model IDs by each provider.

    FAST  -> cheap/quick, high rate limits (most agents).
    SMART -> stronger reasoning, used by the Architect and conflict resolution.
    """

    FAST = "fast"
    SMART = "smart"


@dataclass(slots=True)
class LLMResponse:
    text: str
    model: str
    # Token accounting — used by the dashboard + learning loop. Providers fill
    # whatever they can; missing values stay None.
    input_tokens: int | None = None
    output_tokens: int | None = None
    thinking_tokens: int | None = None
    raw: dict = field(default_factory=dict)


@runtime_checkable
class LLMProvider(Protocol):
    """Minimal async surface every provider must implement."""

    async def generate(
        self,
        *,
        prompt: str,
        system: str | None = None,
        tier: ModelTier = ModelTier.FAST,
        json_output: bool = False,
        thinking_budget: int | None = None,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """Single-shot generation. Implementations must be safe to await concurrently."""
        ...
