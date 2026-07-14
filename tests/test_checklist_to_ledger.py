"""The §22 checklist-to-ledger correctness metric as tests: cross-off inserts
a pantry item through apply_update() with canonical_name user-confirmed and
everything else unknown (absent — never written as an empty estimate)."""

import uuid

import pytest
from fastapi.testclient import TestClient

from backend.app.deps import get_db
from backend.app.main import create_app
from backend.app.models.ledger_change_log import LedgerChangeLog
from backend.app.models.pantry_item import PantryItem
from backend.app.models.shopping_item import ShoppingItem
from backend.app.models.shopping_list import ShoppingList

USER_ID = uuid.uuid4()


@pytest.fixture
def tables(engine):
    from backend.app.db import Base

    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def client(tables, db, monkeypatch):
    monkeypatch.setenv(
        "PANTRYOPS_DATABASE_URL",
        "postgresql+psycopg://pantryops:pantryops@localhost:5432/pantryops",
    )
    monkeypatch.setenv("PANTRYOPS_REDIS_URL", "redis://localhost:6379/0")
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


@pytest.fixture
def confirmed(client, db, tables):
    shopping_list = ShoppingList(user_id=USER_ID, goal="weekly groceries")
    db.add(shopping_list)
    db.flush()
    item = ShoppingItem(
        shopping_list_id=shopping_list.shopping_list_id,
        canonical_name="milk",
        category="dairy",
        unit_label="carton",
        reason="running low",
        priority="high",
        added_by="shopping_planner_agent",
    )
    db.add(item)
    db.commit()
    response = client.post(
        f"/shopping-lists/{shopping_list.shopping_list_id}"
        f"/items/{item.shopping_item_id}/confirm",
        json={"status": "bought"},
    )
    assert response.status_code == 200
    return response.json()


def test_confirm_inserts_pantry_item_via_ledger(db, confirmed):
    pantry = db.get(PantryItem, uuid.UUID(confirmed["pantry_item_id"]))
    assert pantry is not None
    assert pantry.user_id == USER_ID
    assert pantry.canonical_name["value"] == "milk"
    assert pantry.canonical_name["status"] == "user_confirmed"
    assert pantry.canonical_name["source"] == "checklist_cross_off"
    assert pantry.canonical_name["confidence"] == 1.0
    # purchase != product details: unknown fields are ABSENT, never empty estimates
    assert pantry.brand is None
    assert pantry.product_name is None
    assert pantry.quantity_value["source"] == "checklist_default"
    assert pantry.quantity_value["status"] == "estimated"
    assert pantry.status == "bought"


def test_confirm_writes_change_log_rows(db, confirmed):
    rows = db.query(LedgerChangeLog).filter_by(
        pantry_item_id=uuid.UUID(confirmed["pantry_item_id"])
    ).all()
    assert {r.field_name for r in rows} == {"canonical_name", "quantity_value"}
    assert all(r.source is not None for r in rows)
    assert len(rows) == 2


def test_confirm_links_source_event(db, confirmed):
    pantry = db.get(PantryItem, uuid.UUID(confirmed["pantry_item_id"]))
    assert str(pantry.source_event_id) == confirmed["event"]["event_id"]


def test_no_direct_orm_writes():
    """Boundary guard (Phase 2) still green with checklist.py in the tree."""
    from tests.test_ledger_boundary import (
        test_no_direct_change_log_construction_outside_ledger,
        test_no_sourced_field_assignment_outside_ledger,
    )

    test_no_sourced_field_assignment_outside_ledger()
    test_no_direct_change_log_construction_outside_ledger()
