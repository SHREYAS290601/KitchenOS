from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.deps import get_db
from backend.app.models.shopping_item import ShoppingItem
from backend.app.schemas.shopping import (
    ShoppingItemResponse,
    ShoppingListCreate,
    ShoppingListResponse,
)
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
