import uuid

import pytest
from fastapi.testclient import TestClient

from backend.app.deps import get_current_user, get_db
from backend.app.main import create_app
from backend.app.models.pantry_item import PantryItem
from backend.app.schemas.sourced_field import EvidenceSource, FieldStatus, SourcedField

USER_ID = uuid.uuid4()


class FakeUser:
    user_id = USER_ID


def sf(value):
    return SourcedField(
        value=value,
        source=EvidenceSource.user_confirmed,
        confidence=1.0,
        status=FieldStatus.user_confirmed,
    ).model_dump(mode="json")


@pytest.fixture
def client(db, tables, monkeypatch):
    monkeypatch.setenv("PANTRYOPS_DATABASE_URL", "postgresql+psycopg://pantryops:pantryops@localhost:5432/pantryops")
    monkeypatch.setenv("PANTRYOPS_REDIS_URL", "redis://localhost:6379/0")
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: FakeUser()
    return TestClient(app)


def test_vague_usage_asks_correct_question_without_writing(client, db):
    milk = PantryItem(user_id=USER_ID, canonical_name=sf("milk"), quantity_type="capacity_bucket", quantity_value=sf("full"), status="stored")
    tomatoes = PantryItem(user_id=USER_ID, canonical_name=sf("tomatoes"), quantity_type="count", quantity_value=sf(6), status="stored")
    db.add_all([milk, tomatoes])
    db.commit()

    liquid = client.post("/consumption/ad-hoc", json={"message": "I used a lot of milk"}).json()
    count = client.post("/consumption/ad-hoc", json={"message": "I used some tomatoes"}).json()
    db.refresh(milk)

    assert liquid["clarification"]["options"] == ["full", "3/4", "1/2", "1/4", "empty"]
    assert count["clarification"]["question"] == "How many tomatoes are left?"
    assert milk.quantity_value["value"] == "full"


def test_explicit_usage_updates_through_ledger(client, db):
    milk = PantryItem(user_id=USER_ID, canonical_name=sf("milk"), quantity_type="capacity_bucket", quantity_value=sf("full"), status="stored")
    db.add(milk)
    db.commit()
    response = client.post(
        "/consumption/ad-hoc",
        json={"pantry_item_id": str(milk.pantry_item_id), "new_quantity_value": "1/2"},
    )
    assert response.status_code == 200
    assert response.json()["quantity"]["value"] == "1/2"
    assert response.json()["quantity"]["status"] == "user_confirmed"


def test_foreign_consumption_item_is_hidden(client, db):
    item = PantryItem(user_id=uuid.uuid4(), canonical_name=sf("private"), quantity_type="count", status="stored")
    db.add(item)
    db.commit()

    response = client.post(
        "/consumption/ad-hoc",
        json={"pantry_item_id": str(item.pantry_item_id), "new_quantity_value": 0},
    )

    assert response.status_code == 404
