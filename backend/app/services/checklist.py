"""Cross-off -> confirmation event -> (Task 6) ledger insertion, all in one
transaction. The service maps the agent's proposal to apply_update() calls —
the agent itself never touches the ledger."""

import uuid

from sqlalchemy.orm import Session

from backend.app.models.confirmation_event import ShoppingConfirmationEvent
from backend.app.models.shopping_item import ShoppingItem


class ChecklistError(Exception):
    pass


class ItemNotFound(ChecklistError):
    pass


class AlreadyConfirmed(ChecklistError):
    pass


def confirm_item(
    db: Session,
    shopping_list_id: uuid.UUID,
    shopping_item_id: uuid.UUID,
) -> ShoppingConfirmationEvent:
    item = db.get(ShoppingItem, shopping_item_id)
    if item is None or item.shopping_list_id != shopping_list_id:
        raise ItemNotFound(f"shopping item {shopping_item_id} not found in this list")

    existing = db.query(ShoppingConfirmationEvent).filter_by(
        shopping_item_id=shopping_item_id
    ).one_or_none()
    if existing is not None:
        raise AlreadyConfirmed(
            f"{item.canonical_name} was already confirmed — cross-off happens once"
        )

    event = ShoppingConfirmationEvent(
        shopping_item_id=item.shopping_item_id,
        canonical_name=item.canonical_name,
        status="bought",
    )
    db.add(event)
    item.status = "bought"
    item.crossed_off = True
    db.flush()

    db.commit()
    return event
