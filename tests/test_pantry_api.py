import uuid

import pytest
from fastapi.testclient import TestClient

from backend.app.deps import get_current_user, get_db
from backend.app.main import create_app
from backend.app.models.pantry_item import PantryItem
from backend.app.schemas.sourced_field import EvidenceSource, FieldStatus, SourcedField
from backend.app.services.ledger import apply_update

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
def stored_item(db, tables) -> PantryItem:
    item = PantryItem(
        user_id=USER_ID,
        canonical_name=sf("milk", EvidenceSource.checklist_cross_off, 1.0,
                          FieldStatus.user_confirmed),
        brand=sf("Chobani"),
        quantity_type="capacity_bucket",
        status="stored",
    )
    db.add(item)
    db.commit()
    return item


def test_list_items_filters_by_status(client, db, tables, stored_item):
    other = PantryItem(user_id=USER_ID, quantity_type="count", status="planned")
    db.add(other)
    db.commit()

    r = client.get("/pantry/items", params={"status": "stored"})
    assert r.status_code == 200
    ids = [it["pantry_item_id"] for it in r.json()["items"]]
    assert str(stored_item.pantry_item_id) in ids
    assert str(other.pantry_item_id) not in ids


def test_get_item_returns_full_sourced_metadata(client, stored_item):
    r = client.get(f"/pantry/items/{stored_item.pantry_item_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["brand"]["value"] == "Chobani"
    assert body["brand"]["source"] == "label_ocr"
    assert body["brand"]["confidence"] == 0.84
    assert body["brand"]["status"] == "estimated"


def test_get_missing_item_404(client):
    assert client.get(f"/pantry/items/{uuid.uuid4()}").status_code == 404


def test_foreign_item_is_hidden_from_reads_and_mutations(client, db):
    item = PantryItem(user_id=uuid.uuid4(), quantity_type="count", status="stored")
    db.add(item)
    db.commit()

    assert client.get(f"/pantry/items/{item.pantry_item_id}").status_code == 404
    assert client.post(
        f"/pantry/items/{item.pantry_item_id}/quantity",
        json={"quantity_type": "count", "quantity_value": 1, "source": "user_manual_update"},
    ).status_code == 404


def test_quantity_update_applies_user_confirmed(client, stored_item):
    r = client.post(
        f"/pantry/items/{stored_item.pantry_item_id}/quantity",
        json={"quantity_type": "capacity_bucket", "quantity_value": "1/2",
              "source": "user_manual_update"},
    )
    assert r.status_code == 200
    detail = client.get(f"/pantry/items/{stored_item.pantry_item_id}").json()
    assert detail["quantity_value"]["value"] == "1/2"
    assert detail["quantity_value"]["status"] == "user_confirmed"


def test_quantity_update_422_on_bucket_for_count(client, db, tables):
    item = PantryItem(user_id=USER_ID, quantity_type="count", status="stored")
    db.add(item)
    db.commit()

    r = client.post(
        f"/pantry/items/{item.pantry_item_id}/quantity",
        json={"quantity_type": "count", "quantity_value": "1/2",
              "source": "user_manual_update"},
    )
    assert r.status_code == 422
    assert "count" in r.json()["detail"]


def test_field_actions(client, stored_item):
    base = f"/pantry/items/{stored_item.pantry_item_id}/fields/brand"

    r = client.post(base, json={"action": "confirm"})
    assert r.status_code == 200
    assert r.json()["field"]["status"] == "user_confirmed"
    assert r.json()["field"]["value"] == "Chobani"

    r = client.post(base, json={"action": "edit", "value": "Fage"})
    assert r.status_code == 200
    assert r.json()["field"]["status"] == "user_edited"
    assert r.json()["field"]["value"] == "Fage"

    r = client.post(base, json={"action": "leave_as_estimate"})
    assert r.status_code == 200

    r = client.post(base, json={"action": "reject"})
    assert r.status_code == 200
    assert r.json()["field"]["status"] == "rejected"


def test_user_edit_survives_later_estimate(client, db, stored_item):
    base = f"/pantry/items/{stored_item.pantry_item_id}/fields/brand"
    assert client.post(base, json={"action": "edit", "value": "Fage"}).status_code == 200

    # a later background estimate arrives through the ledger
    result = apply_update(
        db, stored_item, "brand",
        SourcedField(value="Chobani", source=EvidenceSource.label_ocr,
                     confidence=0.9, status=FieldStatus.estimated),
        actor="worker",
    )
    db.commit()
    assert result.outcome == "conflict"

    detail = client.get(f"/pantry/items/{stored_item.pantry_item_id}").json()
    assert detail["brand"]["value"] == "Fage"
    assert detail["brand"]["status"] == "user_edited"
    assert detail["brand"]["conflict_candidates"][0]["value"] == "Chobani"
    assert detail["needs_user_review"] is True
