"""Cross-off -> confirmation event -> ledger insertion, all in one
transaction. The service maps the agent's proposal to apply_update() calls —
the agent itself never touches the ledger (invariant 1)."""

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from backend.app.agents.checklist_confirmation import (
    ChecklistConfirmationAgent,
    ConfirmationContext,
)
from backend.app.models.confirmation_event import ShoppingConfirmationEvent
from backend.app.models.pantry_item import PantryItem
from backend.app.models.shopping_item import ShoppingItem
from backend.app.models.shopping_list import ShoppingList
from backend.app.services.ledger import apply_update

CONFIRMATION_ACTOR = "checklist_confirmation_agent"


class ChecklistError(Exception):
    pass


class ItemNotFound(ChecklistError):
    pass


class AlreadyConfirmed(ChecklistError):
    pass


@dataclass(frozen=True)
class ConfirmResult:
    event: ShoppingConfirmationEvent
    pantry_item: PantryItem


def confirm_item(
    db: Session,
    shopping_list_id: uuid.UUID,
    shopping_item_id: uuid.UUID,
) -> ConfirmResult:
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

    shopping_list = db.get(ShoppingList, shopping_list_id)

    event = ShoppingConfirmationEvent(
        shopping_item_id=item.shopping_item_id,
        canonical_name=item.canonical_name,
        status="bought",
    )
    db.add(event)
    item.status = "bought"
    item.crossed_off = True
    db.flush()

    proposal = ChecklistConfirmationAgent().run(
        ConfirmationContext(
            canonical_name=item.canonical_name,
            desired_quantity=item.desired_quantity,
            unit_label=item.unit_label,
            user_id=shopping_list.user_id,
        )
    )

    # Creation path: only the proposal's sourced fields are written; unknown
    # fields stay absent — an empty estimate would be an unsourced write.
    pantry_item = PantryItem(
        user_id=proposal.user_id,
        quantity_type=proposal.quantity_type,
        unit_label=proposal.unit_label,
        status=proposal.lifecycle_status,
        source_event_id=event.event_id,
    )
    db.add(pantry_item)
    db.flush()
    for field_name, sourced in proposal.fields.items():
        apply_update(db, pantry_item, field_name, sourced, actor=CONFIRMATION_ACTOR)

    db.commit()
    return ConfirmResult(event=event, pantry_item=pantry_item)
