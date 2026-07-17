"""Cross-off confirmation (Manifest §6.3, §15.3): confirms purchase ONLY —
the proposal never carries brand, price, or size."""

import uuid

import pytest
from fastapi.testclient import TestClient

from backend.app.deps import get_current_user, get_db
from backend.app.main import create_app
from backend.app.models.confirmation_event import ShoppingConfirmationEvent
from backend.app.models.shopping_item import ShoppingItem
from backend.app.models.shopping_list import ShoppingList

USER_ID = uuid.uuid4()


class FakeUser:
    user_id = USER_ID


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
    app.dependency_overrides[get_current_user] = lambda: FakeUser()
    return TestClient(app)


@pytest.fixture
def planned_item(db, tables) -> ShoppingItem:
    shopping_list = ShoppingList(user_id=USER_ID, goal="weekly groceries")
    db.add(shopping_list)
    db.flush()
    item = ShoppingItem(
        shopping_list_id=shopping_list.shopping_list_id,
        canonical_name="milk",
        category="dairy",
        desired_quantity=None,
        unit_label="carton",
        reason="running low",
        priority="high",
        added_by="shopping_planner_agent",
    )
    db.add(item)
    db.commit()
    return item


def _confirm(client, item: ShoppingItem):
    return client.post(
        f"/shopping-lists/{item.shopping_list_id}/items/{item.shopping_item_id}/confirm",
        json={"status": "bought"},
    )


def test_confirm_creates_event_and_marks_item(client, db, planned_item):
    r = _confirm(client, planned_item)
    assert r.status_code == 200
    data = r.json()
    assert data["event"]["confirmation_source"] == "checklist_cross_off"
    assert data["event"]["confidence"] == 1.0
    assert data["event"]["status"] == "bought"

    db.refresh(planned_item)
    assert planned_item.status == "bought"
    assert planned_item.crossed_off is True
    event = db.query(ShoppingConfirmationEvent).filter_by(
        shopping_item_id=planned_item.shopping_item_id
    ).one()
    assert event.canonical_name == "milk"


def test_double_confirm_409(client, db, planned_item):
    assert _confirm(client, planned_item).status_code == 200
    r = _confirm(client, planned_item)
    assert r.status_code == 409


def test_confirm_missing_item_404(client, db, planned_item):
    r = client.post(
        f"/shopping-lists/{planned_item.shopping_list_id}/items/{uuid.uuid4()}/confirm",
        json={"status": "bought"},
    )
    assert r.status_code == 404


def test_confirm_foreign_list_is_hidden(client, db):
    shopping_list = ShoppingList(user_id=uuid.uuid4(), goal="foreign")
    db.add(shopping_list)
    db.flush()
    item = ShoppingItem(
        shopping_list_id=shopping_list.shopping_list_id,
        canonical_name="secret",
        category="other",
        reason="foreign",
        priority="low",
        added_by="shopping_planner_agent",
    )
    db.add(item)
    db.commit()

    assert _confirm(client, item).status_code == 404


def test_agent_proposal_never_infers_details(planned_item):
    from backend.app.agents.checklist_confirmation import (
        ChecklistConfirmationAgent,
        ConfirmationContext,
    )

    proposal = ChecklistConfirmationAgent().run(
        ConfirmationContext(
            canonical_name="milk",
            desired_quantity=None,
            unit_label="carton",
            user_id=USER_ID,
        )
    )
    assert proposal.fields["canonical_name"].source == "checklist_cross_off"
    assert proposal.fields["canonical_name"].confidence == 1.0
    # purchase != product details: nothing beyond name + the default quantity
    forbidden = {"brand", "product_name", "price", "size", "category", "display_name"}
    assert forbidden.isdisjoint(proposal.fields.keys())
    assert set(proposal.fields.keys()) <= {"canonical_name", "quantity_value"}
