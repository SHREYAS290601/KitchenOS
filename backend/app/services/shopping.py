"""List-creation orchestration: read the ledger, run the planner, persist the
proposal. The planner only ever sees a read-only PantryView slice."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.agents.shopping_planner import (
    FrequentItem,
    PantryView,
    PlannerContext,
    PreferenceRule,
    ShoppingPlannerAgent,
)
from backend.app.models.pantry_item import PantryItem
from backend.app.models.shopping_item import ShoppingItem
from backend.app.models.shopping_list import ShoppingList
from backend.app.schemas.shopping import ShoppingListCreate

PLANNER_ACTOR = "shopping_planner_agent"


def _field_value(field: dict | None) -> str | None:
    return field.get("value") if field else None


def _pantry_views(db: Session, user_id: uuid.UUID) -> list[PantryView]:
    items = db.execute(
        select(PantryItem).where(PantryItem.user_id == user_id)
    ).scalars()
    views = []
    for item in items:
        name = _field_value(item.canonical_name)
        if not name:
            continue
        views.append(
            PantryView(
                canonical_name=name,
                category=_field_value(item.category) or "uncategorized",
                quantity_type=item.quantity_type,
                quantity_value=_field_value(item.quantity_value),
                unit_label=item.unit_label,
            )
        )
    return views


def _frequent_items(db: Session, user_id: uuid.UUID) -> list[FrequentItem]:
    rows = db.execute(
        select(ShoppingItem.canonical_name, ShoppingItem.category)
        .join(ShoppingList, ShoppingItem.shopping_list_id == ShoppingList.shopping_list_id)
        .where(ShoppingList.user_id == user_id)
        .distinct()
    ).all()
    return [FrequentItem(canonical_name=n, category=c) for n, c in rows]


def create_shopping_list(
    db: Session,
    payload: ShoppingListCreate,
    preference_rules: list[PreferenceRule] | None = None,
) -> ShoppingList:
    context = PlannerContext(
        goal=payload.goal,
        pantry=_pantry_views(db, payload.user_id),
        frequent_items=_frequent_items(db, payload.user_id),
        cuisine_preferences=payload.cuisine_preferences,
        dietary_restrictions=payload.dietary_restrictions,
        protein_goal=payload.protein_goal,
        budget=payload.budget,
        preference_rules=preference_rules or [],
    )
    proposal = ShoppingPlannerAgent().run(context)

    shopping_list = ShoppingList(user_id=payload.user_id, goal=payload.goal)
    db.add(shopping_list)
    db.flush()
    for planned in proposal.items:
        db.add(
            ShoppingItem(
                shopping_list_id=shopping_list.shopping_list_id,
                canonical_name=planned.canonical_name,
                category=planned.category,
                desired_quantity=planned.desired_quantity,
                unit_label=planned.unit_label,
                reason=planned.reason,
                priority=planned.priority,
                status=planned.status,
                crossed_off=planned.crossed_off,
                added_by=PLANNER_ACTOR,
            )
        )
    db.commit()
    return shopping_list
