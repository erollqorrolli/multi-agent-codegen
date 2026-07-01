"""Test Agent — writes comprehensive tests against the generated implementation."""

from __future__ import annotations

from app.agents.base import BaseAgent
from app.agents.context import PipelineContext
from app.llm.base import ModelTier
from app.schemas.pipeline import TestOutput


class TestAgent(BaseAgent[TestOutput]):
    name = "test"
    tier = ModelTier.FAST
    output_model = TestOutput

    def system_prompt(self) -> str:
        return (
            "You are a Senior QA / Test Engineer. Write thorough pytest tests: happy paths, "
            "edge cases, auth/permission checks, and failure modes. The tests MUST run in a "
            "clean sandbox with no external services and pass against the code as-is.\n"
            "\n"
            "AVOID THE #1 FAILURE: async DB fixtures bound to the wrong event loop. Do NOT "
            "create an async engine at import/module scope. Prefer SYNCHRONOUS tests using "
            "FastAPI's TestClient over an in-memory SQLite, wired via dependency_overrides. "
            "Use this exact, known-good recipe (adapt names to the app's modules):\n"
            "```python\n"
            "import pytest\n"
            "from fastapi.testclient import TestClient\n"
            "from sqlalchemy import create_engine\n"
            "from sqlalchemy.orm import sessionmaker\n"
            "from sqlalchemy.pool import StaticPool\n"
            "from app.main import app\n"
            "from app.<db module> import Base, get_db  # the app's Base + DB dependency\n"
            "\n"
            "engine = create_engine('sqlite://', connect_args={'check_same_thread': False},\n"
            "                       poolclass=StaticPool)\n"
            "TestingSessionLocal = sessionmaker(bind=engine)\n"
            "\n"
            "@pytest.fixture\n"
            "def client():\n"
            "    Base.metadata.create_all(engine)\n"
            "    def _get_db():\n"
            "        db = TestingSessionLocal()\n"
            "        try: yield db\n"
            "        finally: db.close()\n"
            "    app.dependency_overrides[get_db] = _get_db\n"
            "    with TestClient(app) as c:\n"
            "        yield c\n"
            "    app.dependency_overrides.clear()\n"
            "    Base.metadata.drop_all(engine)\n"
            "```\n"
            "If the app's DB layer is async-only, use httpx.AsyncClient with "
            "ASGITransport and a FUNCTION-scoped async fixture that builds the engine inside "
            "the test's own event loop — never at module scope.\n"
            "Put tests under `tests/`, import from `app...`, require no network."
        )

    def build_task(self, ctx: PipelineContext) -> str:
        impl = ctx.implementation
        assert impl is not None, "Test agent requires implementation context"
        file_list = "\n".join(f"  - {f.path} ({f.language})" for f in impl.files)
        # Include the actual code so tests target real signatures, not guesses.
        bodies = "\n\n".join(
            f"### {f.path}\n```{f.language}\n{f.content}\n```" for f in impl.files
        )
        return (
            f"IMPLEMENTED FILES:\n{file_list}\n\nSOURCE:\n{bodies}\n\n"
            "Produce a JSON object with keys: files (array of {path, content, language}) "
            "containing test files, coverage_notes (string), and validated (boolean: your "
            "best assessment of whether the implementation satisfies the request)."
        )
