from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.orm import Session

from backend.app.models.ledger_change_log import LedgerChangeLog
from backend.app.models.pantry_item import SOURCED_FIELD_COLUMNS, PantryItem
from backend.app.pantry.quantity import QuantityType, validate_quantity
from backend.app.schemas.sourced_field import (
    PRECEDENCE,
    EvidenceSource,
    FieldStatus,
    SourcedField,
)


class LedgerError(ValueError):
    """Raised when an update cannot be accepted as a write at all
    (unsourced payload, non-truth source, unknown field)."""


@dataclass(frozen=True)
class ApplyResult:
    outcome: Literal["applied", "conflict", "rejected"]
    log_row_id: UUID | None = None


_FORBIDDEN_WRITE_SOURCES = {EvidenceSource.llm_inference, EvidenceSource.none}
_USER_SOURCES = {EvidenceSource.user_edited, EvidenceSource.user_confirmed}
_PROTECTED_STATUSES = {FieldStatus.user_confirmed, FieldStatus.user_edited}


def _precedence(source: EvidenceSource) -> int:
    return PRECEDENCE.index(source)


def apply_update(
    session: Session,
    item: PantryItem,
    field_name: str,
    incoming: SourcedField | dict,
    *,
    actor: str,
) -> ApplyResult:
    """THE pantry write path (invariants 1-3, spec architecture.md §8-§9).

    Applies `incoming` iff precedence(incoming.source) is at least as trusted as
    the stored field's source AND the stored status is not user_confirmed/
    user_edited (unless incoming is itself a user action). Otherwise records a
    conflict. Every applied change writes a ledger_change_log row in the same
    transaction.
    """
    if field_name not in SOURCED_FIELD_COLUMNS:
        raise LedgerError(
            f"{field_name!r} is not a sourced pantry field — "
            f"allowed: {', '.join(SOURCED_FIELD_COLUMNS)}"
        )

    if isinstance(incoming, dict):
        try:
            incoming = SourcedField.model_validate(incoming)
        except ValidationError as exc:
            raise LedgerError(
                f"unsourced or malformed update for {field_name!r}: "
                "source, confidence, and status are required"
            ) from exc

    if incoming.source in _FORBIDDEN_WRITE_SOURCES:
        raise LedgerError(
            f"{incoming.source} is not a truth source and can never write the ledger"
        )

    if field_name == "quantity_value":
        validate_quantity(
            QuantityType(item.quantity_type),
            incoming.value,
            unit_label=item.unit_label,
        )

    stored: dict | None = getattr(item, field_name)
    is_user_action = incoming.source in _USER_SOURCES

    if stored is not None and not is_user_action:
        stored_status = stored.get("status")
        stored_source = EvidenceSource(stored.get("source", "none"))

        if stored_status in _PROTECTED_STATUSES:
            candidate = incoming.model_dump(mode="json")
            candidate["status"] = FieldStatus.conflicting
            updated = dict(stored)
            updated.setdefault("conflict_candidates", []).append(candidate)
            setattr(item, field_name, updated)
            item.needs_user_review = True
            session.flush()
            return ApplyResult("conflict")

        if _precedence(incoming.source) > _precedence(stored_source):
            return ApplyResult("rejected")

    old_value = dict(stored) if stored is not None else None
    new_value = incoming.model_dump(mode="json")
    setattr(item, field_name, new_value)

    log_row = LedgerChangeLog(
        pantry_item_id=item.pantry_item_id,
        field_name=field_name,
        old_value=old_value,
        new_value=new_value,
        source=incoming.source,
        confidence=incoming.confidence,
        actor=actor,
    )
    session.add(log_row)
    session.flush()
    return ApplyResult("applied", log_row.id)
