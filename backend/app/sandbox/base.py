"""Sandbox interface + result type, plus shared helpers for writing a file set
to disk and parsing a pytest run. Kept backend-agnostic so Local/Docker share it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable

from app.schemas.pipeline import GeneratedFile

_MAX_OUTPUT = 6000  # truncate captured logs so they fit in DB/prompts


@dataclass(slots=True)
class SandboxResult:
    ran: bool                       # did we actually execute a test command?
    passed: bool                    # all collected tests green (and at least one ran)
    framework: str = "unknown"
    total: int = 0
    passed_count: int = 0
    failed_count: int = 0
    error_count: int = 0
    skipped_count: int = 0
    exit_code: int | None = None
    backend: str = "unknown"
    summary: str = ""               # one-line human summary
    output: str = ""                # truncated stdout+stderr
    details: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "ran": self.ran,
            "passed": self.passed,
            "framework": self.framework,
            "total": self.total,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "error_count": self.error_count,
            "skipped_count": self.skipped_count,
            "backend": self.backend,
            "summary": self.summary,
            "output": self.output,
        }


@runtime_checkable
class Sandbox(Protocol):
    async def run(self, files: list[GeneratedFile]) -> SandboxResult:
        """Materialise `files` and execute their tests in isolation."""
        ...


# --- shared helpers -----------------------------------------------------------
def write_files(root: Path, files: list[GeneratedFile]) -> None:
    """Write a generated file set under `root`, creating subdirectories."""
    for f in files:
        # Refuse path traversal — never write outside the sandbox root.
        target = (root / f.path).resolve()
        if not str(target).startswith(str(root.resolve())):
            raise ValueError(f"unsafe path in generated files: {f.path!r}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f.content)


def detect_framework(files: list[GeneratedFile]) -> str:
    """Best-effort framework detection from the file set."""
    paths = [f.path for f in files]
    if any(re.search(r"(^|/)(test_.*|.*_test)\.py$", p) for p in paths):
        return "pytest"
    if any(p.endswith("package.json") for p in paths):
        return "node"
    return "unknown"


def truncate(text: str) -> str:
    if len(text) <= _MAX_OUTPUT:
        return text
    half = _MAX_OUTPUT // 2
    return text[:half] + "\n…[truncated]…\n" + text[-half:]


def parse_pytest(output: str, exit_code: int) -> dict:
    """Parse pytest's summary line into counts. Robust to colour/ordering."""

    def n(label: str) -> int:
        m = re.search(rf"(\d+)\s+{label}", output)
        return int(m.group(1)) if m else 0

    passed, failed = n("passed"), n("failed")
    errors, skipped = n("error"), n("skipped")
    # exit 5 == "no tests collected"
    collected = passed + failed + errors + skipped
    all_green = exit_code == 0 and passed > 0
    return {
        "passed_count": passed,
        "failed_count": failed,
        "error_count": errors,
        "skipped_count": skipped,
        "total": collected,
        "passed": all_green,
    }
