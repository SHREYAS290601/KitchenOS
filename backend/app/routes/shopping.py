import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from typing import Literal

from backend.app.deps import get_db
from backend.app.models.shopping_item import ShoppingItem
from backend.app.schemas.shopping import (
    ShoppingItemResponse,
    ShoppingListCreate,
    ShoppingListResponse,
)
from backend.app.services.checklist import AlreadyConfirmed, ItemNotFound, confirm_item
from backend.app.services.shopping import create_shopping_list

router = APIRouter(prefix="/shopping-lists", tags=["shopping"])


def _serialize(db: Session, shopping_list) -> ShoppingListResponse:
    items = db.execute(
        select(ShoppingItem)
        .where(ShoppingItem.shopping_list_id == shopping_list.shopping_list_id)
        .order_by(ShoppingItem.canonical_name)
    ).scalars().all()
    return ShoppingListResponse(
        shopping_list_id=shopping_list.shopping_list_id,
        user_id=shopping_list.user_id,
        goal=shopping_list.goal,
        status=shopping_list.status,
        items=[ShoppingItemResponse.model_validate(i) for i in items],
    )


@router.post("", response_model=ShoppingListResponse, status_code=201)
def create_list(payload: ShoppingListCreate, db: Session = Depends(get_db)) -> ShoppingListResponse:
    shopping_list = create_shopping_list(db, payload)
    return _serialize(db, shopping_list)


class ConfirmRequest(BaseModel):
    status: Literal["bought"]


@router.post("/{list_id}/items/{item_id}/confirm")
def confirm(
    list_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: ConfirmRequest,
    db: Session = Depends(get_db),
) -> dict:
    try:
        result = confirm_item(db, list_id, item_id)
    except ItemNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except AlreadyConfirmed as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    event = result.event
    return {
        "event": {
            "event_id": str(event.event_id),
            "shopping_item_id": str(event.shopping_item_id),
            "canonical_name": event.canonical_name,
            "status": event.status,
            "confirmation_source": event.confirmation_source,
            "confidence": event.confidence,
        },
        "pantry_item_id": str(result.pantry_item.pantry_item_id),
    }
