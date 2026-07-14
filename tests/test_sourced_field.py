import pytest
from pydantic import ValidationError

from backend.app.schemas.sourced_field import EvidenceSource, FieldStatus, SourcedField


def test_sourced_field_requires_provenance():
    f = SourcedField(value="Chobani", source=EvidenceSource.label_ocr, confidence=0.84, status=FieldStatus.estimated)
    assert f.editable is True


def test_missing_source_rejected():
    with pytest.raises(ValidationError):
        SourcedField(value="Chobani", confidence=0.84, status=FieldStatus.estimated)


def test_unknown_status_allows_null_value_and_confidence():
    f = SourcedField(value=None, source=EvidenceSource.none, confidence=None, status=FieldStatus.unknown)
    assert f.value is None


def test_confidence_bounds():
    with pytest.raises(ValidationError):
        SourcedField(value="x", source=EvidenceSource.label_ocr, confidence=1.3, status=FieldStatus.estimated)


def test_checklist_default_is_weakest_writable_source():
    """Manifest §14.1: quantity defaults are sourced checklist_default —
    below every real observation, above llm_inference (never writable)."""
    from backend.app.schemas.sourced_field import PRECEDENCE

    idx = PRECEDENCE.index
    assert idx(EvidenceSource.checklist_default) > idx(EvidenceSource.web_enrichment)
    assert idx(EvidenceSource.checklist_default) < idx(EvidenceSource.llm_inference)
