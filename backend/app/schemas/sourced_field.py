from datetime import datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, Field


class FieldStatus(StrEnum):
    estimated = "estimated"
    user_confirmed = "user_confirmed"
    user_edited = "user_edited"
    rejected = "rejected"
    unknown = "unknown"
    conflicting = "conflicting"


class EvidenceSource(StrEnum):
    """Ordered by trust — index in PRECEDENCE decides who wins (spec architecture.md §9)."""
    user_edited = "user_edited"
    user_confirmed = "user_confirmed"
    checklist_cross_off = "checklist_cross_off"
    barcode = "barcode"
    receipt_ocr = "receipt_ocr"
    label_ocr = "label_ocr"
    product_detection = "product_detection"
    segmentation = "segmentation"
    silent_check_in = "silent_check_in"
    api_enrichment = "api_enrichment"
    web_enrichment = "web_enrichment"
    llm_inference = "llm_inference"   # never a truth source
    none = "none"                     # for status=unknown placeholders


PRECEDENCE: list[EvidenceSource] = list(EvidenceSource)  # lower index = higher trust


class SourcedField(BaseModel):
    """Every provenance-carrying value in the system. source/confidence/status are
    REQUIRED — an unsourced write cannot even be constructed (invariant 2)."""

    value: object | None
    source: EvidenceSource
    confidence: float | None = Field(ge=0.0, le=1.0)
    status: FieldStatus
    editable: bool = True
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
