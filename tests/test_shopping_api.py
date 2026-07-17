"""POST /shopping-lists (api-spec.md): 201 with a persisted, categorized list;
every item carries reason and priority; restrictions hold at the API level
(guards the wiring, not just the agent)."""

import uuid

import pytest
from fastapi.testclient import TestClient

from backend.app.deps import get_current_user, get_db
from backend.app.main import create_app
from backend.app.models.pantry_item import PantryItem
from backend.app.models.shopping_item import ShoppingItem
from backend.app.models.shopping_list import ShoppingList
from backend.app.schemas.sourced_field import EvidenceSource, FieldStatus, SourcedField

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


def sf(value, source=EvidenceSource.label_ocr, confidence=0.84,
       status=FieldStatus.estimated) -> dict:
    return SourcedField(value=value, source=source, confidence=confidence,
                        status=status).model_dump(mode="json")


@pytest.fixture
def low_milk(db, tables) -> PantryItem:
    item = PantryItem(
        user_id=USER_ID,
        canonical_name=sf("milk", EvidenceSource.checklist_cross_off, 1.0,
                          FieldStatus.user_confirmed),
        category=sf("dairy"),
        quantity_value=sf("1/4"),
        quantity_type="capacity_bucket",
        status="stored",
    )
    db.add(item)
    db.commit()
    return item


@pytest.fixture
def beef_history(db, tables) -> ShoppingItem:
    """A prior list containing beef — the frequent-item signal the planner
    would normally restock from."""
    prior = ShoppingList(user_id=USER_ID, goal="last week")
    db.add(prior)
    db.flush()
    item = ShoppingItem(
        shopping_list_id=prior.shopping_list_id,
        canonical_name="ground beef",
        category="beef",
        reason="planned meals",
        priority="medium",
        added_by="shopping_planner_agent",
    )
    db.add(item)
    db.commit()
    return item


BODY = {
    "goal": "weekly groceries",
    "cuisine_preferences": ["Indian", "Mexican"],
    "dietary_restrictions": [],
    "protein_goal": "high",
    "budget": 60,
}


def test_create_list_returns_categorized_items_with_reasons(client, db, low_milk):
    r = client.post("/shopping-lists", json=BODY)
    assert r.status_code == 201
    data = r.json()
    assert data["goal"] == "weekly groceries"
    assert data["items"], "low-stock pantry should produce suggestions"
    names = [i["canonical_name"] for i in data["items"]]
    assert "milk" in names
    for item in data["items"]:
        assert item["reason"].strip() != ""
        assert item["priority"] in {"high", "medium", "low"}
        assert item["category"].strip() != ""
        assert item["status"] == "planned"
        assert item["crossed_off"] is False

    persisted = db.query(ShoppingItem).filter_by(
        shopping_list_id=uuid.UUID(data["shopping_list_id"])
    ).all()
    assert {i.canonical_name for i in persisted} == set(names)


def test_create_list_respects_dietary_restrictions(client, db, low_milk, beef_history):
    unrestricted = client.post("/shopping-lists", json=BODY)
    assert "ground beef" in [
        i["canonical_name"] for i in unrestricted.json()["items"]
    ], "beef history should surface without restrictions"

    restricted = client.post(
        "/shopping-lists", json={**BODY, "dietary_restrictions": ["no beef"]}
    )
    assert restricted.status_code == 201
    for item in restricted.json()["items"]:
        assert "beef" not in item["canonical_name"].lower()
        assert "beef" not in item["category"].lower()


def test_create_list_rejects_client_supplied_identity(client):
    response = client.post(
        "/shopping-lists",
        json={**BODY, "user_id": str(uuid.uuid4())},
    )

    assert response.status_code == 422
