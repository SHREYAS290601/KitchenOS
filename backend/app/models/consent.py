import uuid
from datetime import datetime, timezone
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db import Base


class ConsentState(StrEnum):
    not_requested = "not_requested"
    denied = "denied"
    granted_for_single_image = "granted_for_single_image"
    granted_for_session = "granted_for_session"
    always_granted = "always_granted"
    revoked = "revoked"


class RetentionPolicy(StrEnum):
    delete_after_answer = "delete_after_answer"
    delete_after_enrichment = "delete_after_enrichment"
    keep_for_pantry_memory = "keep_for_pantry_memory"
    keep_until_manually_deleted = "keep_until_manually_deleted"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ConsentRecord(Base):
    __tablename__ = "consent_record"
    __table_args__ = (UniqueConstraint("user_id", name="uq_consent_record_user"),)

    consent_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    state: Mapped[str] = mapped_column(String, nullable=False, default=ConsentState.not_requested)
    session_id: Mapped[str | None] = mapped_column(String, nullable=True)
    retention_policy: Mapped[str] = mapped_column(String, nullable=False, default=RetentionPolicy.delete_after_answer)
    single_image_consumed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)
