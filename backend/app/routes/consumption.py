import re
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.agents.consumption_update import ConsumptionClarification, ConsumptionUpdateAgent
from backend.app.deps import get_db
from backend.app.models.pantry_item import PantryItem
from backend.app.pantry.quantity import QuantityError
from backend.app.schemas.sourced_field import EvidenceSource, FieldStatus, SourcedField
from backend.app.services.ledger import apply_update

router = APIRouter(prefix="/consumption/ad-hoc", tags=["consumption"])


class ConsumptionRequest(BaseModel):
    message: str | None = None
    pantry_item_id: uuid.UUID | None = None
    new_quantity_value: str | int | None = None

    @model_validator(mode="after")
    def has_message_or_explicit_update(self):
        if self.message is None and self.pantry_item_id is None:
            raise ValueError("send a message or pantry_item_id with new_quantity_value")
        return self


def _field_name(item: PantryItem) -> str | None:
    return str(item.canonical_name.get("value")) if item.canonical_name else None


def _resolve_message_item(db: Session, message: str) -> PantryItem | None:
    words = set(re.findall(r"[a-z0-9-]+", message.lower()))
    for item in db.execute(select(PantryItem)).scalars():
        name = _field_name(item)
        if name and set(name.lower().split()).issubset(words):
            return item
    return None


@router.post("")
def ad_hoc_consumption(payload: ConsumptionRequest, db: Session = Depends(get_db)) -> dict:
    if payload.pantry_item_id is not None:
        item = db.get(PantryItem, payload.pantry_item_id)
        if item is None:
            raise HTTPException(status_code=404, detail=f"pantry item {payload.pantry_item_id} not found")
        incoming = SourcedField(
            value=payload.new_quantity_value,
            source=EvidenceSource.user_confirmed,
            confidence=1.0,
            status=FieldStatus.user_confirmed,
        )
        try:
            result = apply_update(db, item, "quantity_value", incoming, actor="user")
        except QuantityError as exc:
            db.rollback()
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        db.commit()
        return {"outcome": result.outcome, "quantity": item.quantity_value}

    item = _resolve_message_item(db, payload.message or "")
    if item is None:
        return {
            "clarification": ConsumptionClarification(
                question="Which pantry item did you use?",
                input_type="item_selection",
            ).model_dump()
        }
    name = _field_name(item) or "item"
    clarification = ConsumptionUpdateAgent().clarify(name, item.quantity_type)
    return {
        "pantry_item_id": str(item.pantry_item_id),
        "clarification": clarification.model_dump(),
    }
