"""Shared API dependencies — currently optional bearer-token auth.

Auth is OFF when `API_TOKEN` is unset (convenient for local dev and the demo).
Set `API_TOKEN` in production and send it as `Authorization: Bearer <token>` or
`X-API-Key: <token>` to protect the endpoints.
"""

from __future__ import annotations

import hmac

from fastapi import Header, HTTPException

from app.config import get_settings


def _token_ok(expected: str, authorization: str | None, x_api_key: str | None) -> bool:
    if not expected:
        return True  # auth disabled
    presented = x_api_key
    if authorization and authorization.lower().startswith("bearer "):
        presented = authorization[7:].strip()
    return bool(presented) and hmac.compare_digest(presented, expected)


async def require_api_token(
    authorization: str | None = Header(default=None),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> None:
    if not _token_ok(get_settings().api_token, authorization, x_api_key):
        raise HTTPException(status_code=401, detail="missing or invalid API token")
