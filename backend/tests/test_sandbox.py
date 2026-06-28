"""Proof that the sandbox actually executes generated tests.

These run the LocalSandbox against a synthetic "generated" file set — a passing
suite and a deliberately failing one — and assert it distinguishes them. No
Docker, no API key, no network required.
"""

from __future__ import annotations

import pytest

from app.sandbox.base import detect_framework, parse_pytest
from app.sandbox.local import LocalSandbox
from app.schemas.pipeline import GeneratedFile

# A tiny self-contained "generated project": implementation + its test.
_IMPL = GeneratedFile(
    path="calculator.py",
    content="def add(a, b):\n    return a + b\n",
    language="python",
)
_PASSING_TEST = GeneratedFile(
    path="test_calculator.py",
    content="from calculator import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n",
    language="python",
)
_FAILING_TEST = GeneratedFile(
    path="test_calculator.py",
    content="from calculator import add\n\n\ndef test_add():\n    assert add(2, 3) == 6  # wrong on purpose\n",
    language="python",
)


@pytest.mark.asyncio
async def test_sandbox_reports_passing_suite():
    result = await LocalSandbox(install_deps=False).run([_IMPL, _PASSING_TEST])
    assert result.ran is True
    assert result.passed is True
    assert result.passed_count == 1
    assert result.failed_count == 0
    assert result.backend == "local"


@pytest.mark.asyncio
async def test_sandbox_catches_failing_suite():
    result = await LocalSandbox(install_deps=False).run([_IMPL, _FAILING_TEST])
    assert result.ran is True
    assert result.passed is False          # <-- the whole point: a lie is caught
    assert result.failed_count == 1


@pytest.mark.asyncio
async def test_sandbox_handles_no_tests():
    result = await LocalSandbox(install_deps=False).run([_IMPL])  # no test file
    assert result.ran is False
    assert result.passed is False


def test_detect_framework():
    assert detect_framework([_PASSING_TEST]) == "pytest"
    assert detect_framework([GeneratedFile(path="package.json", content="{}")]) == "node"
    assert detect_framework([_IMPL]) == "unknown"


def test_parse_pytest_summary():
    parsed = parse_pytest("=== 3 passed, 1 failed, 2 skipped in 0.1s ===", exit_code=1)
    assert parsed["passed_count"] == 3
    assert parsed["failed_count"] == 1
    assert parsed["skipped_count"] == 2
    assert parsed["passed"] is False
