"""A deterministic, offline LLM provider for tests.

Returns canned structured output per agent (detected from the system prompt), so
the full pipeline — orchestration, fix loop, sandbox, learning loop — can be
exercised with no API key, no network, and no quota.
"""

from __future__ import annotations

import json

from app.llm.base import LLMResponse, ModelTier

_ARCHITECTURE = {
    "tech_stack": ["Python", "FastAPI"],
    "data_models": "User(id, email)",
    "api_endpoints": ["POST /add - add two numbers"],
    "components": ["api", "service"],
    "rationale": "Minimal, conventional stack.",
}
_TEST = {
    "files": [
        {
            "path": "test_calculator.py",
            "content": "from calculator import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n",
            "language": "python",
        }
    ],
    "coverage_notes": "Covers addition.",
    "validated": True,
}
_SECURITY = {"findings": [], "passed": True}
_OPTIMIZATION = {
    "suggestions": [
        {"area": "db", "issue": "no index", "improvement": "add index", "estimated_impact": "high"}
    ]
}
_LESSONS = {"lessons": [{"agent": "security", "lesson": "Always rate-limit auth endpoints."}]}


def _impl(content: str) -> dict:
    return {
        "files": [{"path": "calculator.py", "content": content, "language": "python"}],
        "notes": "implemented add()",
    }


_GOOD_ADD = "def add(a, b):\n    return a + b\n"
_BUGGY_ADD = "def add(a, b):\n    return a + b + 1  # off by one\n"


class StubProvider:
    """Implements the LLMProvider protocol with fixed responses.

    `buggy_first=True` makes the first implementation fail its tests, so the fix
    loop has to revise (it returns correct code once it sees a REVISING prompt).
    """

    def __init__(self, *, buggy_first: bool = False) -> None:
        self.buggy_first = buggy_first
        self.calls: list[str] = []

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
        s = system or ""
        if "Architect" in s:
            agent, payload = "architect", _ARCHITECTURE
        elif "Backend Engineer" in s:
            agent = "implementation"
            revising = "REVISING" in prompt
            good = revising or not self.buggy_first
            payload = _impl(_GOOD_ADD if good else _BUGGY_ADD)
        elif "Test Engineer" in s:
            agent, payload = "test", _TEST
        elif "Security Engineer" in s:
            agent, payload = "security", _SECURITY
        elif "Performance Engineer" in s:
            agent, payload = "optimization", _OPTIMIZATION
        elif "PR feedback" in s:
            agent, payload = "lessons", _LESSONS
        else:
            agent, payload = "unknown", {}

        self.calls.append(agent)
        return LLMResponse(text=json.dumps(payload), model="stub", input_tokens=10, output_tokens=5)
