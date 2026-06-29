"""Google Gemini provider (Google AI Studio free tier).

Uses the unified `google-genai` SDK. Key behaviours we care about for a
multi-agent system on the *free* tier:

  * async via `client.aio` so 5 agents can fan out without blocking the loop;
  * automatic retry/backoff on 429 (free tier has tight per-minute limits);
  * optional "thinking budget" (Gemini 2.5 reasoning) for hard agents;
  * structured JSON output via response_mime_type.
"""

from __future__ import annotations

import logging

from google import genai
from google.genai import types
from google.genai.errors import APIError
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from app.llm.base import LLMProvider, LLMResponse, ModelTier

logger = logging.getLogger(__name__)


def _is_rate_limit(exc: BaseException) -> bool:
    """Retry only on 429 / resource-exhausted — not on bad requests."""
    return isinstance(exc, APIError) and getattr(exc, "code", None) in (429, 503)


class GeminiProvider(LLMProvider):
    def __init__(
        self,
        *,
        api_key: str,
        model_fast: str,
        model_smart: str,
        thinking_budget_fast: int,
        thinking_budget_smart: int,
    ) -> None:
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY is empty. Get a free key at "
                "https://aistudio.google.com/apikey and set it in .env"
            )
        self._client = genai.Client(api_key=api_key)
        self._models = {ModelTier.FAST: model_fast, ModelTier.SMART: model_smart}
        self._thinking_budget = {
            ModelTier.FAST: thinking_budget_fast,
            ModelTier.SMART: thinking_budget_smart,
        }

    def _model_for(self, tier: ModelTier) -> str:
        return self._models[tier]

    @retry(
        retry=retry_if_exception(_is_rate_limit),
        wait=wait_exponential(multiplier=2, min=2, max=60),
        stop=stop_after_attempt(5),
        reraise=True,
    )
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
        model = self._model_for(tier)
        budget = self._thinking_budget[tier] if thinking_budget is None else thinking_budget

        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            response_mime_type="application/json" if json_output else "text/plain",
            thinking_config=types.ThinkingConfig(thinking_budget=budget),
        )

        logger.debug("Gemini generate model=%s tier=%s json=%s", model, tier, json_output)
        resp = await self._client.aio.models.generate_content(
            model=model,
            contents=prompt,
            config=config,
        )

        usage = getattr(resp, "usage_metadata", None)
        return LLMResponse(
            text=resp.text or "",
            model=model,
            input_tokens=getattr(usage, "prompt_token_count", None),
            output_tokens=getattr(usage, "candidates_token_count", None),
            thinking_tokens=getattr(usage, "thoughts_token_count", None),
            raw={"finish_reason": str(getattr(resp.candidates[0], "finish_reason", ""))}
            if resp.candidates
            else {},
        )
