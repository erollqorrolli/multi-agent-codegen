"""LocalSandbox — runs generated tests in a temp dir via a subprocess.

No Docker required, so it works on any dev machine and in CI. It does NOT provide
strong isolation (the code runs as your user), so it's the dev/CI fallback —
DockerSandbox is the right choice for untrusted code in production.

Optionally creates a throwaway virtualenv and pip-installs a generated
requirements.txt so FastAPI-style projects can import their deps.
"""

from __future__ import annotations

import asyncio
import logging
import sys
import tempfile
from pathlib import Path

from app.sandbox.base import (
    SandboxResult,
    detect_framework,
    parse_pytest,
    truncate,
    write_files,
)
from app.schemas.pipeline import GeneratedFile

logger = logging.getLogger(__name__)


class LocalSandbox:
    def __init__(self, *, timeout: int = 120, install_deps: bool = True) -> None:
        self._timeout = timeout
        self._install_deps = install_deps

    async def run(self, files: list[GeneratedFile]) -> SandboxResult:
        framework = detect_framework(files)
        if framework != "pytest":
            return SandboxResult(
                ran=False,
                passed=False,
                framework=framework,
                backend="local",
                summary=f"No runnable pytest suite detected (framework={framework}).",
            )

        with tempfile.TemporaryDirectory(prefix="codegen-sbx-") as tmp:
            root = Path(tmp)
            write_files(root, files)

            python = sys.executable
            logs: list[str] = []

            # Optionally install a generated requirements.txt into the active env.
            req = root / "requirements.txt"
            if self._install_deps and req.exists():
                code, out = await self._exec(
                    [python, "-m", "pip", "install", "-q", "-r", str(req)], root
                )
                logs.append(f"$ pip install -r requirements.txt (exit {code})\n{out}")

            code, out = await self._exec([python, "-m", "pytest", "-q"], root)
            logs.append(f"$ pytest -q (exit {code})\n{out}")

            parsed = parse_pytest(out, code)
            combined = truncate("\n\n".join(logs))
            return SandboxResult(
                ran=True,
                passed=parsed["passed"],
                framework="pytest",
                total=parsed["total"],
                passed_count=parsed["passed_count"],
                failed_count=parsed["failed_count"],
                error_count=parsed["error_count"],
                skipped_count=parsed["skipped_count"],
                exit_code=code,
                backend="local",
                summary=_summary(parsed, code),
                output=combined,
            )

    async def _exec(self, cmd: list[str], cwd: Path) -> tuple[int, str]:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(cwd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        try:
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=self._timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return 124, f"TIMEOUT after {self._timeout}s"
        return proc.returncode or 0, stdout.decode(errors="replace")


def _summary(parsed: dict, exit_code: int) -> str:
    if exit_code == 5:
        return "No tests collected."
    return (
        f"{parsed['passed_count']} passed, {parsed['failed_count']} failed, "
        f"{parsed['error_count']} error, {parsed['skipped_count']} skipped"
    )
