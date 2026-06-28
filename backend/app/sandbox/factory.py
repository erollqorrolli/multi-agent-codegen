"""Sandbox backend selection.

`auto` (default) prefers Docker for real isolation but transparently falls back
to the local subprocess runner when the Docker daemon isn't present — so the
pipeline never breaks on a machine without Docker.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from app.config import get_settings
from app.sandbox.base import Sandbox

logger = logging.getLogger(__name__)


@lru_cache
def get_sandbox() -> Sandbox:
    settings = get_settings()
    backend = settings.sandbox_backend.lower()

    from app.sandbox.docker import DockerSandbox
    from app.sandbox.local import LocalSandbox

    if backend == "docker":
        return DockerSandbox(timeout=settings.sandbox_timeout)
    if backend == "local":
        return LocalSandbox(timeout=settings.sandbox_timeout)

    # auto
    if DockerSandbox.available():
        logger.info("sandbox: using Docker backend")
        return DockerSandbox(timeout=settings.sandbox_timeout)
    logger.warning("sandbox: Docker not found, falling back to local subprocess backend")
    return LocalSandbox(timeout=settings.sandbox_timeout)
