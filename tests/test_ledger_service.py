import uuid

import pytest
from sqlalchemy import func, select

from backend.app.models.ledger_change_log import LedgerChangeLog
from backend.app.models.pantry_item import PantryItem
from backend.app.pantry.quantity import QuantityError
from backend.app.schemas.sourced_field import EvidenceSource, FieldStatus, SourcedField
from backend.app.services.ledger import ApplyResult, LedgerError, apply_update


@pytest.fixture
def tables(engine):
    from backend.app.db import Base

    Base.metadata.create_all(engine)
    return engine


def sf(value, source, confidence=0.8, status=FieldStatus.estimated) -> SourcedField:
    return SourcedField(value=value, source=source, confidence=confidence, status=status)


@pytest.fixture
def item(tables, db) -> PantryItem:
    it = PantryItem(user_id=uuid.uuid4(), quantity_type="count", status="stored")
    db.add(it)
    db.commit()
    return it


def log_count(db, item) -> int:
    return db.execute(
        select(func.count(LedgerChangeLog.id)).where(
            LedgerChangeLog.pantry_item_id == item.pantry_item_id
        )
    ).scalar_one()


def test_estimate_fills_unknown_field(db, item):
    result = apply_update(db, item, "brand",
                          sf("Chobani", EvidenceSource.label_ocr, 0.84), actor="worker")
    assert result.outcome == "applied"
    assert item.brand["value"] == "Chobani"
    assert result.log_row_id is not None


def test_user_edit_beats_any_estimate(db, item):
    apply_update(db, item, "brand",
                 sf("Chobani", EvidenceSource.barcode, 0.97), actor="worker")
    result = apply_update(
        db, item, "brand",
        sf("Fage", EvidenceSource.user_edited, 1.0, FieldStatus.user_edited),
        actor="user")
    assert result.outcome == "applied"
    assert item.brand["value"] == "Fage"
    assert item.brand["status"] == "user_edited"


def test_estimate_never_overwrites_user_confirmed(db, item):
    apply_update(
        db, item, "brand",
        sf("Fage", EvidenceSource.user_confirmed, 1.0, FieldStatus.user_confirmed),
        actor="user")
    result = apply_update(db, item, "brand",
                          sf("Chobani", EvidenceSource.label_ocr, 0.84), actor="worker")
    assert result.outcome == "conflict"
    assert item.brand["value"] == "Fage"
    assert item.brand["status"] == "user_confirmed"
    assert item.brand["conflict_candidates"][0]["value"] == "Chobani"
    assert item.brand["conflict_candidates"][0]["status"] == "conflicting"
    assert item.needs_user_review is True


def test_barcode_beats_label_ocr(db, item):
    apply_update(db, item, "brand",
                 sf("Chobani", EvidenceSource.label_ocr, 0.84), actor="worker")
    result = apply_update(db, item, "brand",
                          sf("Chobani Inc", EvidenceSource.barcode, 0.97), actor="worker")
    assert result.outcome == "applied"
    assert item.brand["value"] == "Chobani Inc"


def test_label_ocr_does_not_beat_barcode(db, item):
    apply_update(db, item, "brand",
                 sf("Chobani Inc", EvidenceSource.barcode, 0.97), actor="worker")
    result = apply_update(db, item, "brand",
                          sf("Chobani", EvidenceSource.label_ocr, 0.84), actor="worker")
    assert result.outcome == "rejected"
    assert item.brand["value"] == "Chobani Inc"


def test_llm_inference_never_applies(db, item):
    with pytest.raises(LedgerError, match="llm_inference"):
        apply_update(db, item, "brand",
                     sf("Guessed", EvidenceSource.llm_inference, 0.5), actor="agent")


def test_unsourced_update_rejected(db, item):
    with pytest.raises(LedgerError, match="source"):
        apply_update(db, item, "brand",
                     {"value": "Chobani", "confidence": 0.84, "status": "estimated"},
                     actor="worker")


def test_every_applied_update_writes_exactly_one_log_row(db, item):
    apply_update(db, item, "brand",
                 sf("Chobani", EvidenceSource.label_ocr, 0.84), actor="worker")
    assert log_count(db, item) == 1
    apply_update(db, item, "brand",
                 sf("Chobani Inc", EvidenceSource.barcode, 0.97), actor="worker")
    assert log_count(db, item) == 2


def test_rejected_update_writes_no_log_row_but_records_conflict(db, item):
    apply_update(
        db, item, "brand",
        sf("Fage", EvidenceSource.user_confirmed, 1.0, FieldStatus.user_confirmed),
        actor="user")
    before = log_count(db, item)
    result = apply_update(db, item, "brand",
                          sf("Chobani", EvidenceSource.label_ocr, 0.84), actor="worker")
    assert result.outcome == "conflict"
    assert result.log_row_id is None
    assert log_count(db, item) == before
    assert item.brand["conflict_candidates"]


def test_quantity_update_validates_against_quantity_type(db, item):
    assert item.quantity_type == "count"
    with pytest.raises(QuantityError, match="count"):
        apply_update(db, item, "quantity_value",
                     sf("1/2", EvidenceSource.silent_check_in, 0.6), actor="worker")
