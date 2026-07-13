import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, String, Uuid, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db import Base


class LedgerChangeLog(Base):
    """Append-only audit row (data-models.md §4.2): one per applied field
    change, written in the same transaction by apply_update(). No UPDATE or
    DELETE path — the ORM listeners below raise on both."""

    __tablename__ = "ledger_change_log"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    pantry_item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("pantry_item.pantry_item_id"), index=True
    )
    field_name: Mapped[str] = mapped_column(String)
    old_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    new_value: Mapped[dict] = mapped_column(JSONB)
    source: Mapped[str] = mapped_column(String)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    actor: Mapped[str] = mapped_column(String)  # user | agent | worker
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class AppendOnlyViolation(RuntimeError):
    pass


@event.listens_for(LedgerChangeLog, "before_update")
def _forbid_update(mapper, connection, target):
    raise AppendOnlyViolation(
        "ledger_change_log is append-only — rows cannot be updated"
    )


@event.listens_for(LedgerChangeLog, "before_delete")
def _forbid_delete(mapper, connection, target):
    raise AppendOnlyViolation(
        "ledger_change_log is append-only — rows cannot be deleted"
    )
