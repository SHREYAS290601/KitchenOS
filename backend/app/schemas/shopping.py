import uuid

from pydantic import BaseModel, Field


class ShoppingListCreate(BaseModel):
    user_id: uuid.UUID
    goal: str
    cuisine_preferences: list[str] = Field(default_factory=list)
    dietary_restrictions: list[str] = Field(default_factory=list)
    protein_goal: str | None = None
    budget: float | None = None


class ShoppingItemResponse(BaseModel):
    shopping_item_id: uuid.UUID
    canonical_name: str
    category: str
    desired_quantity: int | None
    unit_label: str | None
    reason: str
    priority: str
    status: str
    crossed_off: bool
    added_by: str

    model_config = {"from_attributes": True}


class ShoppingListResponse(BaseModel):
    shopping_list_id: uuid.UUID
    user_id: uuid.UUID
    goal: str
    status: str
    items: list[ShoppingItemResponse]
