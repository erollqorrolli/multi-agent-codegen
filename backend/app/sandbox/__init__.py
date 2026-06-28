"""Sandboxed execution of generated tests.

The Test agent can claim a build is valid, but claims are cheap. This package
*runs* the generated tests in isolation and returns a real pass/fail signal that
the orchestrator uses to drive its fix loop.

Two interchangeable backends behind one `Sandbox` interface:
  * DockerSandbox — strong isolation (resource limits, no privileges); for prod.
  * LocalSandbox  — subprocess in a temp dir; zero-infra fallback for dev/CI.
"""

from app.sandbox.base import Sandbox, SandboxResult
from app.sandbox.factory import get_sandbox

__all__ = ["Sandbox", "SandboxResult", "get_sandbox"]
