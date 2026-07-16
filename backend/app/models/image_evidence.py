import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ImageEvidenceRecord(Base):
    __tablename__ = "image_evidence"

    image_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    capture_context: Mapped[str] = mapped_column(String, nullable=False)
    processing_mode: Mapped[str] = mapped_column(String, nullable=False)
    linked_shopping_session_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    related_item_candidate: Mapped[str | None] = mapped_column(String, nullable=True)
    storage_uri: Mapped[str] = mapped_column(String, nullable=False)
    consent_status: Mapped[str] = mapped_column(String, nullable=False)
    retention_policy: Mapped[str] = mapped_column(String, nullable=False)
    stored_for_future_enrichment: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
