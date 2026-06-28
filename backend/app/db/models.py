"""ORM models.

The schema is deliberately built around *observability* and the *learning loop*:
every agent step is persisted so the dashboard can replay a run, and every PR
outcome becomes a `Feedback` row that distills into `LearnedLesson`s which are
injected into future prompts.
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _uuid() -> str:
    return str(uuid.uuid4())


class RunStatus(enum.StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class FeedbackVerdict(enum.StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    CHANGES_REQUESTED = "changes_requested"


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)

    # Source of the request — a GitHub issue, or a manual/local trigger.
    repo: Mapped[str | None] = mapped_column(String(255))
    issue_number: Mapped[int | None] = mapped_column(Integer)
    issue_title: Mapped[str] = mapped_column(String(512))
    issue_body: Mapped[str] = mapped_column(Text, default="")

    status: Mapped[RunStatus] = mapped_column(
        Enum(RunStatus, native_enum=False), default=RunStatus.PENDING
    )
    error: Mapped[str | None] = mapped_column(Text)

    # Final artifacts (the PR we open, plus the generated file set).
    pr_url: Mapped[str | None] = mapped_column(String(512))
    generated_files: Mapped[dict] = mapped_column(JSON, default=dict)

    total_input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_output_tokens: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    steps: Mapped[list["AgentStep"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="AgentStep.sequence"
    )
    feedback: Mapped[list["Feedback"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class AgentStep(Base):
    """One agent's contribution within a run — persisted for replay/debugging."""

    __tablename__ = "agent_steps"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    run_id: Mapped[str] = mapped_column(ForeignKey("pipeline_runs.id", ondelete="CASCADE"))

    sequence: Mapped[int] = mapped_column(Integer)
    agent: Mapped[str] = mapped_column(String(64))          # "architect", "implementation", ...
    model: Mapped[str | None] = mapped_column(String(128))
    output: Mapped[dict] = mapped_column(JSON, default=dict)  # structured agent result
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[int | None] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    run: Mapped[PipelineRun] = relationship(back_populates="steps")


class Feedback(Base):
    """A human verdict on a generated PR — the raw signal for the learning loop."""

    __tablename__ = "feedback"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    run_id: Mapped[str] = mapped_column(ForeignKey("pipeline_runs.id", ondelete="CASCADE"))

    verdict: Mapped[FeedbackVerdict] = mapped_column(Enum(FeedbackVerdict, native_enum=False))
    comment: Mapped[str] = mapped_column(Text, default="")
    # Optional structured review payload (e.g. GitHub review threads).
    details: Mapped[dict] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    run: Mapped[PipelineRun] = relationship(back_populates="feedback")


class LearnedLesson(Base):
    """Distilled guidance derived from feedback, injected into future prompts.

    This is the persisted memory of the learning loop: short, reusable rules
    like "always add rate limiting to auth endpoints" scoped to an agent.
    """

    __tablename__ = "learned_lessons"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    agent: Mapped[str] = mapped_column(String(64))     # which agent this guides
    lesson: Mapped[str] = mapped_column(Text)
    # Higher = surfaced first / weighted more in prompt assembly.
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    times_applied: Mapped[int] = mapped_column(Integer, default=0)
    source_run_id: Mapped[str | None] = mapped_column(String(36))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
