"""Security Agent — audits the generated code for vulnerabilities/bad patterns."""

from __future__ import annotations

from app.agents.base import BaseAgent
from app.agents.context import PipelineContext
from app.llm.base import ModelTier
from app.schemas.pipeline import SecurityOutput


class SecurityAgent(BaseAgent[SecurityOutput]):
    name = "security"
    tier = ModelTier.SMART  # reasoning matters for spotting subtle flaws
    output_model = SecurityOutput

    def system_prompt(self) -> str:
        return (
            "You are an Application Security Engineer. Audit the provided code for "
            "vulnerabilities and insecure patterns: injection, broken authn/authz, secrets "
            "in code, missing input validation, insecure deserialization, missing rate "
            "limiting, weak crypto, SSRF, and OWASP Top 10 issues generally. Report only "
            "real, actionable findings. If the code is sound, return passed=true with an "
            "empty findings list."
        )

    def build_task(self, ctx: PipelineContext) -> str:
        impl = ctx.implementation
        assert impl is not None, "Security agent requires implementation context"
        bodies = "\n\n".join(
            f"### {f.path}\n```{f.language}\n{f.content}\n```" for f in impl.files
        )
        return (
            f"CODE UNDER REVIEW:\n{bodies}\n\n"
            "Produce a JSON object with keys: findings (array of {severity, issue, "
            "location, fix}) where severity is one of critical|high|medium|low|info, and "
            "passed (boolean: false if any high/critical finding exists)."
        )
