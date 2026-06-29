"""Provider selection. Add a new vendor here and the rest of the app gains it."""

from __future__ import annotations

from functools import lru_cache

from app.config import get_settings
from app.llm.base import LLMProvider


@lru_cache
def get_llm_provider() -> LLMProvider:
    settings = get_settings()
    provider = settings.llm_provider.lower()

    if provider == "gemini":
        from app.llm.gemini import GeminiProvider

        return GeminiProvider(
            api_key=settings.gemini_api_key,
            model_fast=settings.gemini_model_fast,
            model_smart=settings.gemini_model_smart,
            thinking_budget_fast=settings.llm_thinking_budget,
            thinking_budget_smart=settings.llm_thinking_budget_smart,
            max_output_tokens=settings.llm_max_output_tokens,
        )

    # To add Claude/OpenAI: implement LLMProvider in app/llm/<vendor>.py and
    # return it here. No agent code changes.
    raise ValueError(f"Unknown LLM_PROVIDER={settings.llm_provider!r}")
