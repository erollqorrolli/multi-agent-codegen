"""LLM provider abstraction.

Agents depend on the `LLMProvider` protocol, never on a concrete vendor SDK.
Swap Gemini for Claude/OpenAI by adding one adapter and registering it in factory.py.
"""

from app.llm.base import LLMProvider, LLMResponse, ModelTier
from app.llm.factory import get_llm_provider

__all__ = ["LLMProvider", "LLMResponse", "ModelTier", "get_llm_provider"]
