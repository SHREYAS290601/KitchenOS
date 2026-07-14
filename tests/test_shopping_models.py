"""Shopping models (data-models.md §4.3): every generated item carries a
reason and priority; no duplicate planned items per list."""

import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from backend.app.db import Base
from backend.app.models.shopping_item import ShoppingItem
from backend.app.models.shopping_list import ShoppingList


@pytest.fixture(autouse=True)
def _tables(engine):
    Base.metadata.create_all(engine)


def _list(**overrides) -> ShoppingList:
    defaults = {"user_id": uuid.uuid4(), "goal": "weekly groceries"}
    return ShoppingList(**{**defaults, **overrides})


def _item(shopping_list_id, **overrides) -> ShoppingItem:
    defaults = {
        "shopping_list_id": shopping_list_id,
        "canonical_name": "tomatoes",
        "category": "produce",
        "desired_quantity": 4,
        "unit_label": "tomatoes",
        "reason": "needed for planned recipes",
        "priority": "high",
        "added_by": "shopping_planner_agent",
    }
    return ShoppingItem(**{**defaults, **overrides})


def test_list_round_trips_with_items(db):
    shopping_list = _list()
    db.add(shopping_list)
    db.flush()
    db.add(_item(shopping_list.shopping_list_id))
    db.add(_item(shopping_list.shopping_list_id, canonical_name="milk", category="dairy"))
    db.commit()

    items = db.query(ShoppingItem).order_by(ShoppingItem.canonical_name).all()
    assert [i.canonical_name for i in items] == ["milk", "tomatoes"]
    assert all(i.shopping_list_id == shopping_list.shopping_list_id for i in items)


@pytest.mark.parametrize("required", ["category", "reason", "priority"])
def test_item_requires_categorization_fields(db, required):
    shopping_list = _list()
    db.add(shopping_list)
    db.flush()
    db.add(_item(shopping_list.shopping_list_id, **{required: None}))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_item_defaults(db):
    shopping_list = _list()
    db.add(shopping_list)
    db.flush()
    item = _item(shopping_list.shopping_list_id)
    db.add(item)
    db.commit()
    assert item.crossed_off is False
    assert item.status == "planned"


def test_no_duplicate_planned_items_per_list(db):
    shopping_list = _list()
    db.add(shopping_list)
    db.flush()
    db.add(_item(shopping_list.shopping_list_id))
    db.commit()
    db.add(_item(shopping_list.shopping_list_id))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
