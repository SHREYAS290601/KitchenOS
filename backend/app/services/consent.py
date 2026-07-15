import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.consent import ConsentRecord, ConsentState, RetentionPolicy


@dataclass(frozen=True)
class ConsentSnapshot:
    state: ConsentState
    session_id: str | None = None
    retention_policy: RetentionPolicy = RetentionPolicy.delete_after_answer


def _find(db: Session, user_id: uuid.UUID) -> ConsentRecord | None:
    return db.execute(select(ConsentRecord).where(ConsentRecord.user_id == user_id)).scalar_one_or_none()


def get_state(db: Session, user_id: uuid.UUID) -> ConsentSnapshot:
    row = _find(db, user_id)
    if row is None:
        return ConsentSnapshot(ConsentState.not_requested)
    return ConsentSnapshot(ConsentState(row.state), row.session_id, RetentionPolicy(row.retention_policy))


def grant(
    db: Session,
    user_id: uuid.UUID,
    state: ConsentState,
    *,
    session_id: str | None = None,
    retention_policy: RetentionPolicy = RetentionPolicy.delete_after_answer,
) -> ConsentRecord:
    if state not in {
        ConsentState.granted_for_single_image,
        ConsentState.granted_for_session,
        ConsentState.always_granted,
        ConsentState.denied,
    }:
        raise ValueError(f"cannot grant consent state {state}")
    if state == ConsentState.granted_for_session and not session_id:
        raise ValueError("granted_for_session requires session_id")
    row = _find(db, user_id) or ConsentRecord(user_id=user_id)
    row.state = state
    row.session_id = session_id if state == ConsentState.granted_for_session else None
    row.retention_policy = retention_policy
    row.single_image_consumed = False
    db.add(row)
    db.commit()
    return row


def revoke(db: Session, user_id: uuid.UUID) -> ConsentRecord:
    row = _find(db, user_id) or ConsentRecord(user_id=user_id)
    row.state = ConsentState.revoked
    row.session_id = None
    db.add(row)
    db.commit()
    return row


def check_can_store(db: Session, user_id: uuid.UUID, session_id: str | None) -> bool:
    row = _find(db, user_id)
    if row is None:
        return False
    state = ConsentState(row.state)
    if state == ConsentState.always_granted:
        return True
    if state == ConsentState.granted_for_session:
        return bool(session_id and row.session_id == session_id)
    if state == ConsentState.granted_for_single_image:
        return not row.single_image_consumed
    return False


def consume_single_image_grant(db: Session, row: ConsentRecord) -> None:
    if ConsentState(row.state) == ConsentState.granted_for_single_image:
        row.single_image_consumed = True
        db.add(row)
        db.flush()
