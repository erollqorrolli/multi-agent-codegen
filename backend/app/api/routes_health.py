from __future__ import annotations

from fastapi import APIRouter

from app import __version__
from app.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    s = get_settings()
    return {
        "status": "ok",
        "version": __version__,
        "llm_provider": s.llm_provider,
        "env": s.app_env,
    }
