"""Checklist Confirmation Agent (agents.md §3): builds the pantry-insertion
proposal from a cross-off. Purchase != product details (Manifest §15.3) —
the proposal carries canonical_name and a low-confidence quantity default,
NEVER brand, price, size, or product identity."""

import uuid

from pydantic import BaseModel

from backend.app.schemas.sourced_field import EvidenceSource, FieldStatus, SourcedField


class ConfirmationContext(BaseModel):
    canonical_name: str
    desired_quantity: int | None = None
    unit_label: str | None = None
    user_id: uuid.UUID


class PantryInsertionProposal(BaseModel):
    user_id: uuid.UUID
    fields: dict[str, SourcedField]
    quantity_type: str
    unit_label: str | None
    lifecycle_status: str = "bought"


class ChecklistConfirmationAgent:
    def run(self, context: ConfirmationContext) -> PantryInsertionProposal:
        fields: dict[str, SourcedField] = {
            "canonical_name": SourcedField(
                value=context.canonical_name,
                source=EvidenceSource.checklist_cross_off,
                confidence=1.0,
                status=FieldStatus.user_confirmed,
            ),
        }
        if context.desired_quantity is not None:
            quantity_type = "count"
            default_value: str | int = context.desired_quantity
        else:
            quantity_type = "capacity_bucket"
            default_value = "full"
        fields["quantity_value"] = SourcedField(
            value=default_value,
            source=EvidenceSource.checklist_default,
            confidence=0.7,
            status=FieldStatus.estimated,
        )
        return PantryInsertionProposal(
            user_id=context.user_id,
            fields=fields,
            quantity_type=quantity_type,
            unit_label=context.unit_label,
        )
