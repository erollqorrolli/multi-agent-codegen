"""GitHub App integration.

Three jobs:
  1. verify_signature — authenticate incoming webhooks (HMAC-SHA256);
  2. app/installation auth — mint a JWT from the App private key, exchange it for
     a short-lived installation token;
  3. open_pull_request — commit a set of generated files onto a new branch and
     open a PR, atomically, via the Git Data API.

Only depends on httpx + PyJWT so it stays easy to test.
"""

from __future__ import annotations

import base64
import hmac
import logging
import time
from hashlib import sha256
from pathlib import Path

import httpx
import jwt

from app.config import get_settings
from app.schemas.pipeline import GeneratedFile

logger = logging.getLogger(__name__)
_API = "https://api.github.com"


def verify_signature(payload: bytes, signature_header: str | None) -> bool:
    """Validate the `X-Hub-Signature-256` header against the webhook secret."""
    secret = get_settings().github_webhook_secret
    if not secret or not signature_header:
        return False
    expected = "sha256=" + hmac.new(secret.encode(), payload, sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header)


def _app_jwt() -> str:
    """Short-lived JWT identifying the App itself (RS256, signed by private key)."""
    settings = get_settings()
    key = Path(settings.github_private_key_path).read_text()
    now = int(time.time())
    payload = {"iat": now - 60, "exp": now + 540, "iss": settings.github_app_id}
    return jwt.encode(payload, key, algorithm="RS256")


class GitHubClient:
    """Authenticated as a specific installation of the App."""

    def __init__(self, token: str) -> None:
        self._client = httpx.AsyncClient(
            base_url=_API,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=30,
        )

    @classmethod
    async def for_installation(cls, installation_id: int) -> "GitHubClient":
        async with httpx.AsyncClient(base_url=_API, timeout=30) as c:
            resp = await c.post(
                f"/app/installations/{installation_id}/access_tokens",
                headers={
                    "Authorization": f"Bearer {_app_jwt()}",
                    "Accept": "application/vnd.github+json",
                },
            )
            resp.raise_for_status()
            return cls(resp.json()["token"])

    async def aclose(self) -> None:
        await self._client.aclose()

    async def open_pull_request(
        self,
        *,
        repo: str,  # "owner/name"
        branch: str,
        title: str,
        body: str,
        files: list[GeneratedFile],
        commit_message: str,
    ) -> str:
        """Commit `files` to a new `branch` and open a PR. Returns the PR URL."""
        # 1) base branch + its tip SHA
        repo_info = (await self._get(f"/repos/{repo}")).json()
        base = repo_info["default_branch"]
        base_sha = (await self._get(f"/repos/{repo}/git/ref/heads/{base}")).json()["object"]["sha"]
        base_commit = (await self._get(f"/repos/{repo}/git/commits/{base_sha}")).json()
        base_tree = base_commit["tree"]["sha"]

        # 2) blobs -> tree -> commit
        tree_entries = []
        for f in files:
            blob = (
                await self._post(
                    f"/repos/{repo}/git/blobs",
                    {"content": base64.b64encode(f.content.encode()).decode(), "encoding": "base64"},
                )
            ).json()
            tree_entries.append(
                {"path": f.path, "mode": "100644", "type": "blob", "sha": blob["sha"]}
            )
        new_tree = (
            await self._post(
                f"/repos/{repo}/git/trees", {"base_tree": base_tree, "tree": tree_entries}
            )
        ).json()
        commit = (
            await self._post(
                f"/repos/{repo}/git/commits",
                {"message": commit_message, "tree": new_tree["sha"], "parents": [base_sha]},
            )
        ).json()

        # 3) branch ref -> PR
        await self._post(
            f"/repos/{repo}/git/refs", {"ref": f"refs/heads/{branch}", "sha": commit["sha"]}
        )
        pr = (
            await self._post(
                f"/repos/{repo}/pulls",
                {"title": title, "head": branch, "base": base, "body": body},
            )
        ).json()
        logger.info("Opened PR %s", pr.get("html_url"))
        return pr["html_url"]

    # --- thin HTTP helpers ----------------------------------------------------
    async def _get(self, path: str) -> httpx.Response:
        resp = await self._client.get(path)
        resp.raise_for_status()
        return resp

    async def _post(self, path: str, json_body: dict) -> httpx.Response:
        resp = await self._client.post(path, json=json_body)
        resp.raise_for_status()
        return resp
