from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.deps import get_db
from backend.app.models.pantry_item import SOURCED_FIELD_COLUMNS, PantryItem
from backend.app.pantry.quantity import QuantityError
from backend.app.schemas.sourced_field import EvidenceSource, FieldStatus, SourcedField
from backend.app.services.ledger import LedgerError, apply_update

router = APIRouter(prefix="/pantry", tags=["pantry"])


def _serialize(item: PantryItem) -> dict:
    """SourcedFields go out verbatim — estimates are never hidden (Guardrail 8)."""
    return {
        "pantry_item_id": str(item.pantry_item_id),
        "user_id": str(item.user_id),
        **{name: getattr(item, name) for name in SOURCED_FIELD_COLUMNS},
        "quantity_type": item.quantity_type,
        "unit_label": item.unit_label,
        "purchase_date": item.purchase_date.isoformat() if item.purchase_date else None,
        "storage_location": item.storage_location,
        "estimated_use_by": (
            item.estimated_use_by.isoformat() if item.estimated_use_by else None
        ),
        "status": item.status,
        "needs_user_review": item.needs_user_review,
    }


def _get_item(db: Session, item_id: UUID) -> PantryItem:
    item = db.get(PantryItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"pantry item {item_id} not found")
    return item


@router.get("/items")
def list_items(status: str | None = None, db: Session = Depends(get_db)) -> dict:
    query = select(PantryItem).order_by(PantryItem.created_at)
    if status is not None:
        query = query.where(PantryItem.status == status)
    items = db.execute(query).scalars().all()
    return {"items": [_serialize(item) for item in items]}


@router.get("/items/{item_id}")
def get_item(item_id: UUID, db: Session = Depends(get_db)) -> dict:
    return _serialize(_get_item(db, item_id))


class QuantityUpdate(BaseModel):
    quantity_type: Literal["count", "capacity_bucket", "unknown"]
    quantity_value: str | int | None
    source: Literal["user_manual_update"]


@router.post("/items/{item_id}/quantity")
def update_quantity(
    item_id: UUID, payload: QuantityUpdate, db: Session = Depends(get_db)
) -> dict:
    item = _get_item(db, item_id)
    item.quantity_type = payload.quantity_type
    incoming = SourcedField(
        value=payload.quantity_value,
        source=EvidenceSource.user_confirmed,
        confidence=1.0,
        status=FieldStatus.user_confirmed,
    )
    try:
        result = apply_update(db, item, "quantity_value", incoming, actor="user")
    except QuantityError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc))
    db.commit()
    return {"outcome": result.outcome, "field": item.quantity_value}


class FieldAction(BaseModel):
    action: Literal["confirm", "edit", "reject", "leave_as_estimate"]
    value: str | int | None = None


@router.post("/items/{item_id}/fields/{field_name}")
def field_action(
    item_id: UUID, field_name: str, payload: FieldAction,
    db: Session = Depends(get_db),
) -> dict:
    item = _get_item(db, item_id)
    if field_name not in SOURCED_FIELD_COLUMNS:
        raise HTTPException(
            status_code=404,
            detail=f"{field_name!r} is not a reviewable field — "
            f"use one of {', '.join(SOURCED_FIELD_COLUMNS)}",
        )
    stored: dict | None = getattr(item, field_name)

    if payload.action == "leave_as_estimate":
        return {"outcome": "left_as_estimate", "field": stored}

    if payload.action == "confirm":
        if stored is None:
            raise HTTPException(
                status_code=409,
                detail=f"{field_name} has no value to confirm — edit it instead",
            )
        incoming = SourcedField(
            value=stored["value"], source=EvidenceSource.user_confirmed,
            confidence=1.0, status=FieldStatus.user_confirmed,
        )
    elif payload.action == "edit":
        incoming = SourcedField(
            value=payload.value, source=EvidenceSource.user_edited,
            confidence=1.0, status=FieldStatus.user_edited,
        )
    else:  # reject
        incoming = SourcedField(
            value=None, source=EvidenceSource.user_edited,
            confidence=1.0, status=FieldStatus.rejected,
        )

    try:
        result = apply_update(db, item, field_name, incoming, actor="user")
    except (LedgerError, QuantityError) as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc))
    db.commit()
    return {"outcome": result.outcome, "field": getattr(item, field_name)}
