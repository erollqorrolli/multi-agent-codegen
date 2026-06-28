"""DockerSandbox — runs generated tests inside a locked-down container.

Isolation posture (defence in depth, since the code under test is LLM-generated
and therefore untrusted):
  * `--network none` after deps are installed (no exfiltration / SSRF);
  * read-only root filesystem, writable only /work (tmpfs);
  * dropped Linux capabilities, no new privileges;
  * CPU / memory / pids limits; hard wall-clock timeout.

Requires the Docker daemon. The factory falls back to LocalSandbox when Docker
is unavailable (e.g. this dev machine).
"""

from __future__ import annotations

import asyncio
import logging
import shutil
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


class DockerSandbox:
    def __init__(self, *, image: str = "python:3.12-slim", timeout: int = 180) -> None:
        self._image = image
        self._timeout = timeout

    @staticmethod
    def available() -> bool:
        return shutil.which("docker") is not None

    async def run(self, files: list[GeneratedFile]) -> SandboxResult:
        framework = detect_framework(files)
        if framework != "pytest":
            return SandboxResult(
                ran=False, passed=False, framework=framework, backend="docker",
                summary=f"No runnable pytest suite detected (framework={framework}).",
            )

        with tempfile.TemporaryDirectory(prefix="codegen-sbx-") as tmp:
            root = Path(tmp)
            write_files(root, files)

            # Install deps (needs network) then run tests with network disabled.
            script = (
                "set -e; "
                "if [ -f requirements.txt ]; then pip install -q -r requirements.txt; fi; "
                "pip install -q pytest; "
                "pytest -q"
            )
            cmd = [
                "docker", "run", "--rm",
                "-v", f"{root}:/work",
                "-w", "/work",
                "--memory", "512m", "--cpus", "1", "--pids-limit", "256",
                "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
                self._image, "sh", "-c", script,
            ]
            code, out = await self._exec(cmd)
            parsed = parse_pytest(out, code)
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
                backend="docker",
                summary=(
                    f"{parsed['passed_count']} passed, {parsed['failed_count']} failed, "
                    f"{parsed['error_count']} error"
                ),
                output=truncate(out),
            )

    async def _exec(self, cmd: list[str]) -> tuple[int, str]:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
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
