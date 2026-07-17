from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.app.schemas.sourced_field import EvidenceSource, FieldStatus, SourcedField

LOW_CONFIDENCE_THRESHOLD = 0.75
SourcedFieldName = Literal[
    "canonical_name",
    "display_name",
    "category",
    "brand",
    "product_name",
    "quantity_value",
]


class EnrichmentCandidate(BaseModel):
    model_config = ConfigDict(frozen=True)

    field_name: SourcedFieldName
    value: object | None
    confidence: float = Field(ge=0, le=1)


class EnrichmentContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    candidates: tuple[EnrichmentCandidate, ...]


class SourcedCandidate(BaseModel):
    model_config = ConfigDict(frozen=True)

    field_name: SourcedFieldName
    field: SourcedField


class BackgroundEnrichmentProposal(BaseModel):
    model_config = ConfigDict(frozen=True)

    candidates: tuple[SourcedCandidate, ...]
    needs_user_review: bool


class BackgroundEnrichmentAgent:
    """Turns untrusted step output into typed estimates; never writes the ORM."""

    def run(self, context: EnrichmentContext) -> BackgroundEnrichmentProposal:
        candidates = tuple(
            SourcedCandidate(
                field_name=candidate.field_name,
                field=SourcedField(
                    value=candidate.value,
                    source=EvidenceSource.silent_check_in,
                    confidence=candidate.confidence,
                    status=FieldStatus.estimated,
                ),
            )
            for candidate in context.candidates
        )
        return BackgroundEnrichmentProposal(
            candidates=candidates,
            needs_user_review=any(
                candidate.confidence < LOW_CONFIDENCE_THRESHOLD
                for candidate in context.candidates
            ),
        )
