import uuid

import pytest

from backend.app.models.ledger_change_log import LedgerChangeLog
from backend.app.models.pantry_item import PantryItem
from backend.app.schemas.sourced_field import EvidenceSource, FieldStatus, SourcedField


def make_sf(value, source=EvidenceSource.checklist_cross_off, confidence=1.0,
            status=FieldStatus.user_confirmed) -> dict:
    return SourcedField(
        value=value, source=source, confidence=confidence, status=status
    ).model_dump(mode="json")


@pytest.fixture
def tables(engine):
    from backend.app.db import Base

    Base.metadata.create_all(engine)
    return engine


def test_pantry_item_jsonb_round_trip(tables, db):
    item = PantryItem(
        user_id=uuid.uuid4(),
        canonical_name=make_sf("milk"),
        brand=make_sf("Chobani", source=EvidenceSource.label_ocr,
                      confidence=0.84, status=FieldStatus.estimated),
        quantity_type="capacity_bucket",
        quantity_value=make_sf("full"),
        status="stored",
    )
    db.add(item)
    db.commit()

    loaded = db.get(PantryItem, item.pantry_item_id)
    assert loaded.canonical_name["value"] == "milk"
    assert loaded.canonical_name["source"] == "checklist_cross_off"
    assert loaded.brand["confidence"] == 0.84
    assert loaded.needs_user_review is False


def test_change_log_round_trip_and_append_only(tables, db):
    item = PantryItem(
        user_id=uuid.uuid4(),
        canonical_name=make_sf("rice"),
        quantity_type="count",
        status="planned",
    )
    db.add(item)
    db.commit()

    row = LedgerChangeLog(
        pantry_item_id=item.pantry_item_id,
        field_name="brand",
        old_value=None,
        new_value=make_sf("Basmati Co", source=EvidenceSource.barcode,
                          confidence=0.97, status=FieldStatus.estimated),
        source="barcode",
        confidence=0.97,
        actor="worker",
    )
    db.add(row)
    db.commit()

    loaded = db.get(LedgerChangeLog, row.id)
    assert loaded.new_value["value"] == "Basmati Co"

    with pytest.raises(Exception, match="append-only"):
        db.delete(loaded)
        db.flush()
    db.rollback()

    loaded = db.get(LedgerChangeLog, row.id)
    loaded.field_name = "tampered"
    with pytest.raises(Exception, match="append-only"):
        db.flush()
    db.rollback()
