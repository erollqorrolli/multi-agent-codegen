"""GitHub webhook entrypoint.

Receives `issues` events, verifies the signature, and (for newly opened issues)
kicks off the pipeline in the background, then opens a PR with the result.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.orchestrator import Orchestrator
from app.db.models import PipelineRun
from app.db.session import SessionLocal, get_session
from app.llm import get_llm_provider
from app.schemas.pipeline import GenerationRequest
from app.services.github import GitHubClient, verify_signature

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/webhook", tags=["webhook"])


@router.post("/github")
async def github_webhook(
    request: Request,
    background: BackgroundTasks,
    x_github_event: str = Header(default=""),
    x_hub_signature_256: str | None = Header(default=None),
    _session: AsyncSession = Depends(get_session),
) -> dict:
    raw = await request.body()
    if not verify_signature(raw, x_hub_signature_256):
        raise HTTPException(401, "invalid signature")

    payload = await request.json()

    # Only act on newly opened issues (ignore comments, edits, our own PRs, etc.)
    if x_github_event != "issues" or payload.get("action") != "opened":
        return {"ignored": True, "event": x_github_event, "action": payload.get("action")}

    issue = payload["issue"]
    repo = payload["repository"]["full_name"]
    installation_id = payload["installation"]["id"]

    req = GenerationRequest(
        issue_title=issue["title"],
        issue_body=issue.get("body") or "",
        repo=repo,
        issue_number=issue["number"],
    )
    background.add_task(_run_pipeline_and_open_pr, req, installation_id)
    return {"accepted": True, "repo": repo, "issue": issue["number"]}


async def _run_pipeline_and_open_pr(req: GenerationRequest, installation_id: int) -> None:
    """Background worker: own its own DB session (request session is closed)."""
    async with SessionLocal() as session:
        orchestrator = Orchestrator(get_llm_provider(), session)
        try:
            result = await orchestrator.run(req)
        except Exception:
            logger.exception("Pipeline failed for issue %s", req.issue_number)
            return

        gh = await GitHubClient.for_installation(installation_id)
        try:
            pr_url = await gh.open_pull_request(
                repo=req.repo or "",
                branch=f"codegen/issue-{req.issue_number}",
                title=f"Resolve #{req.issue_number}: {req.issue_title}",
                body=result.pr_body,
                files=[*result.implementation.files, *result.tests.files],
                commit_message=f"feat: implement #{req.issue_number} via multi-agent pipeline",
            )
            run = await session.get(PipelineRun, result.run_id)
            if run:
                run.pr_url = pr_url
                await session.commit()
        finally:
            await gh.aclose()
