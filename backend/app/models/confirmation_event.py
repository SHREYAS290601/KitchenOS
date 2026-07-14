import uuid
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ShoppingConfirmationEvent(Base):
    """The highest-trust purchase signal (data-models.md §4.4). Cross-off
    confirms purchase only — never brand, price, size, or nutrition. One
    confirmation per shopping item; the API turns a second attempt into 409."""

    __tablename__ = "shopping_confirmation_event"
    __table_args__ = (
        CheckConstraint(
            "confirmation_source = 'checklist_cross_off'",
            name="ck_confirmation_source_cross_off",
        ),
        CheckConstraint("confidence = 1.0", name="ck_confirmation_confidence_full"),
    )

    event_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    shopping_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("shopping_item.shopping_item_id"), unique=True
    )
    canonical_name: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    confirmation_source: Mapped[str] = mapped_column(
        String, default="checklist_cross_off", nullable=False
    )
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
