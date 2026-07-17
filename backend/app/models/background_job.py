import uuid
from datetime import datetime, timezone
from enum import StrEnum

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db import Base


class JobStatus(StrEnum):
    queued = "queued"
    processing = "processing"
    completed = "completed"
    failed = "failed"
    needs_review = "needs_review"


class StepStatus(StrEnum):
    queued = "queued"
    processing = "processing"
    completed = "completed"
    failed = "failed"


CHECK_IN_STEPS = (
    "image_storage",
    "segmentation",
    "object_detection",
    "ocr",
    "barcode",
    "product_enrichment",
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def initial_check_in_steps() -> list[dict[str, str]]:
    return [
        {
            "step": step,
            "status": (
                StepStatus.completed.value
                if step == "image_storage"
                else StepStatus.queued.value
            ),
        }
        for step in CHECK_IN_STEPS
    ]


class BackgroundJob(Base):
    __tablename__ = "background_job"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'processing', 'completed', 'failed', 'needs_review')",
            name="ck_background_job_status",
        ),
        CheckConstraint(
            "dispatch_attempts >= 0",
            name="ck_background_job_dispatch_attempts_nonnegative",
        ),
        Index("ix_background_job_dispatch", "status", "dispatched_at", "created_at"),
    )

    job_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    job_type: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default="grocery_image_check_in",
    )
    status: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default=JobStatus.queued,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    image_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    steps: Mapped[list[dict[str, str]]] = mapped_column(
        JSONB,
        nullable=False,
        default=initial_check_in_steps,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dispatch_claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dispatch_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    retention_enforced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def set_step_status(self, step: str, status: StepStatus | str) -> None:
        if step not in CHECK_IN_STEPS:
            raise ValueError(f"unknown check-in step: {step}")
        try:
            resolved_status = StepStatus(status)
        except ValueError as exc:
            raise ValueError(f"unknown step status: {status}") from exc

        self.steps = [
            {**entry, "status": resolved_status.value}
            if entry["step"] == step
            else dict(entry)
            for entry in self.steps
        ]

    def all_steps_completed(self) -> bool:
        return bool(self.steps) and all(
            entry["status"] == StepStatus.completed.value for entry in self.steps
        )
