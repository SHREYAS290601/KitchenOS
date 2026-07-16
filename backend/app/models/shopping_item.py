import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ShoppingItem(Base):
    """One planned item (data-models.md §4.3). Every generated item carries a
    reason and priority; (list, canonical_name) is unique — no duplicate
    planned items."""

    __tablename__ = "shopping_item"
    __table_args__ = (
        UniqueConstraint(
            "shopping_list_id", "canonical_name", name="uq_shopping_item_per_list"
        ),
    )

    shopping_item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    shopping_list_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("shopping_list.shopping_list_id"), index=True
    )

    canonical_name: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str] = mapped_column(String, nullable=False)
    desired_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    unit_label: Mapped[str | None] = mapped_column(String, nullable=True)
    reason: Mapped[str] = mapped_column(String, nullable=False)
    priority: Mapped[str] = mapped_column(String, nullable=False)

    status: Mapped[str] = mapped_column(String, default="planned")
    crossed_off: Mapped[bool] = mapped_column(Boolean, default=False)
    added_by: Mapped[str] = mapped_column(String, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
