"""Pure-function smoke tests — no DB, no network, no API key required.

These guard the parsing/coordination glue that the LLM output flows through.
Run with: `pytest` from the backend/ directory.
"""

from __future__ import annotations

from app.agents.base import _extract_json
from app.schemas.pipeline import (
    ArchitectOutput,
    GeneratedFile,
    GenerationRequest,
    ImplementationOutput,
    OptimizationOutput,
    PipelineResult,
    SecurityFinding,
    SecurityOutput,
    TestOutput,
)
from app.services.github import verify_signature
from app.services.pr_builder import build_pr_body


def test_extract_json_plain():
    assert _extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_with_code_fence():
    fenced = '```json\n{"a": 1, "b": [2, 3]}\n```'
    assert _extract_json(fenced) == {"a": 1, "b": [2, 3]}


def test_extract_json_with_surrounding_prose():
    messy = 'Sure! Here is the result:\n{"ok": true}\nHope that helps.'
    assert _extract_json(messy) == {"ok": True}


def test_verify_signature_rejects_when_no_secret():
    # No secret configured -> never trust an unsigned/forged payload.
    assert verify_signature(b"{}", "sha256=deadbeef") is False
    assert verify_signature(b"{}", None) is False


def test_build_pr_body_includes_security_status():
    result = PipelineResult(
        run_id="r1",
        architecture=ArchitectOutput(tech_stack=["FastAPI", "Postgres"], rationale="Solid."),
        implementation=ImplementationOutput(
            files=[GeneratedFile(path="main.py", content="print(1)", language="python")]
        ),
        tests=TestOutput(files=[], validated=True, coverage_notes="covered"),
        security=SecurityOutput(
            findings=[SecurityFinding(severity="high", issue="SQLi", fix="parametrize")],
            passed=False,
        ),
        optimization=OptimizationOutput(),
    )
    body = build_pr_body(
        GenerationRequest(issue_title="Build expense API"), result
    )
    assert "Build expense API" in body
    assert "SQLi" in body
    assert "FastAPI" in body
