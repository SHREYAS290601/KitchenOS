import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PantryItem(Base):
    """The ledger row (data-models.md §4.1). SourcedField JSONB columns hold
    {value, source, confidence, status, editable, last_updated} dicts and are
    written ONLY by services/ledger.py::apply_update()."""

    __tablename__ = "pantry_item"

    pantry_item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)

    canonical_name: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    display_name: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    category: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    brand: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    product_name: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    quantity_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    quantity_type: Mapped[str] = mapped_column(String, default="unknown")
    unit_label: Mapped[str | None] = mapped_column(String, nullable=True)
    purchase_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    storage_location: Mapped[str | None] = mapped_column(String, nullable=True)
    estimated_use_by: Mapped[date | None] = mapped_column(Date, nullable=True)

    status: Mapped[str] = mapped_column(String, default="planned", index=True)
    source_event_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    needs_user_review: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


SOURCED_FIELD_COLUMNS: tuple[str, ...] = (
    "canonical_name",
    "display_name",
    "category",
    "brand",
    "product_name",
    "quantity_value",
)
