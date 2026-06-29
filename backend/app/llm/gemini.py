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

from app.llm.base import LLMProvider, LLMResponse, ModelTier, QuotaExceededError

logger = logging.getLogger(__name__)


def _is_daily_quota(exc: BaseException) -> bool:
    """A *per-day* quota cap — retrying within the request is pointless."""
    return isinstance(exc, APIError) and "PerDay" in str(exc)


def _is_retryable(exc: BaseException) -> bool:
    """Retry transient 429/503 (per-minute limits), but NOT a daily quota cap."""
    return (
        isinstance(exc, APIError)
        and getattr(exc, "code", None) in (429, 503)
        and not _is_daily_quota(exc)
    )


def _quota_message(exc: BaseException) -> str:
    return (
        "Gemini quota exhausted (likely the free-tier daily request limit). "
        "It resets at midnight US Pacific. To continue now, create a new API key in a "
        "fresh Google AI Studio project (new project = fresh quota), or use a paid plan."
    )


class GeminiProvider(LLMProvider):
    def __init__(
        self,
        *,
        api_key: str,
        model_fast: str,
        model_smart: str,
        thinking_budget_fast: int,
        thinking_budget_smart: int,
        max_output_tokens: int = 32768,
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
        self._max_output_tokens = max_output_tokens

    def _model_for(self, tier: ModelTier) -> str:
        return self._models[tier]

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
        """Public entrypoint: retries transient limits, surfaces quota clearly."""
        try:
            return await self._generate_once(
                prompt=prompt,
                system=system,
                tier=tier,
                json_output=json_output,
                thinking_budget=thinking_budget,
                temperature=temperature,
            )
        except APIError as exc:
            if getattr(exc, "code", None) == 429:
                raise QuotaExceededError(_quota_message(exc)) from exc
            raise

    @retry(
        retry=retry_if_exception(_is_retryable),
        wait=wait_exponential(multiplier=2, min=2, max=60),
        stop=stop_after_attempt(5),
        reraise=True,
    )
    async def _generate_once(
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
            max_output_tokens=self._max_output_tokens,
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
