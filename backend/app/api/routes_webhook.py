"""GitHub webhook entrypoint.

Verifies the signature, then:
  * `issues/opened`  -> run the pipeline and open a PR;
  * `pull_request/closed` -> feed the merge/close back into the learning loop.
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
from app.services.learning import feedback_from_pr

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
    action = payload.get("action")

    # Issue opened -> generate + open a PR.
    if x_github_event == "issues" and action == "opened":
        issue = payload["issue"]
        req = GenerationRequest(
            issue_title=issue["title"],
            issue_body=issue.get("body") or "",
            repo=payload["repository"]["full_name"],
            issue_number=issue["number"],
        )
        background.add_task(_run_pipeline_and_open_pr, req, payload["installation"]["id"])
        return {"accepted": True, "repo": req.repo, "issue": issue["number"]}

    # PR closed -> learning loop (merged = accepted, closed = rejected).
    if x_github_event == "pull_request" and action == "closed":
        pr = payload["pull_request"]
        background.add_task(_handle_pr_closed, pr["html_url"], bool(pr.get("merged")))
        return {"accepted": True, "pr": pr["html_url"], "merged": bool(pr.get("merged"))}

    return {"ignored": True, "event": x_github_event, "action": action}


async def _handle_pr_closed(pr_url: str, merged: bool) -> None:
    """Background worker: convert a closed PR into learning-loop feedback."""
    async with SessionLocal() as session:
        try:
            fb = await feedback_from_pr(
                session, get_llm_provider(), pr_url=pr_url, merged=merged
            )
            if fb:
                logger.info("Recorded %s feedback for PR %s", fb.verdict, pr_url)
        except Exception:
            logger.exception("Failed to process closed PR %s", pr_url)


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
