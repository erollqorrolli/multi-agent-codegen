"""Typed I/O contracts for the agent pipeline.

Each agent emits a structured object (validated against these models) which is
handed to the next agent. Structured hand-off — not free text — is what lets the
agents *coordinate*: the Test agent reads the Implementation agent's file list,
the Security agent reads both, and so on.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


# ---- Pipeline input ----------------------------------------------------------
class GenerationRequest(BaseModel):
    issue_title: str = Field(..., description="Short description, e.g. the GitHub issue title")
    issue_body: str = Field("", description="Full requirements / acceptance criteria")
    repo: str | None = None
    issue_number: int | None = None


# ---- Generated code ----------------------------------------------------------
class GeneratedFile(BaseModel):
    path: str
    content: str
    language: str = "text"


# ---- Per-agent outputs -------------------------------------------------------
class ArchitectOutput(BaseModel):
    tech_stack: list[str] = Field(default_factory=list)
    data_models: str = Field("", description="Schema / entity description (DDL or prose)")
    api_endpoints: list[str] = Field(default_factory=list)
    components: list[str] = Field(default_factory=list)
    rationale: str = ""


class ImplementationOutput(BaseModel):
    files: list[GeneratedFile] = Field(default_factory=list)
    notes: str = ""


class TestOutput(BaseModel):
    __test__ = False  # stop pytest from trying to collect this as a test class
    files: list[GeneratedFile] = Field(default_factory=list)
    coverage_notes: str = ""
    validated: bool = False


class SecurityFinding(BaseModel):
    severity: str = Field(..., description="critical | high | medium | low | info")
    issue: str
    location: str = ""
    fix: str = ""


class SecurityOutput(BaseModel):
    findings: list[SecurityFinding] = Field(default_factory=list)
    passed: bool = True


class OptimizationSuggestion(BaseModel):
    area: str
    issue: str
    improvement: str
    estimated_impact: str = ""


class OptimizationOutput(BaseModel):
    suggestions: list[OptimizationSuggestion] = Field(default_factory=list)


# ---- Aggregate ---------------------------------------------------------------
class PipelineResult(BaseModel):
    run_id: str
    architecture: ArchitectOutput
    implementation: ImplementationOutput
    tests: TestOutput
    security: SecurityOutput
    optimization: OptimizationOutput
    # Real sandbox execution result of the generated tests (None if disabled).
    test_execution: dict | None = None
    pr_body: str = ""
