import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.consent import ConsentRecord, ConsentState, RetentionPolicy
from backend.app.models.image_evidence import ImageEvidenceRecord
from backend.app.services.consent import check_can_store, consume_single_image_grant
from backend.app.storage.base import ObjectStore


class ConsentRequired(PermissionError):
    pass


def store_image(
    db: Session,
    store: ObjectStore,
    *,
    user_id: uuid.UUID,
    image_bytes: bytes,
    content_type: str,
    capture_context: str,
    shopping_session_id: str | None,
    retention_policy: RetentionPolicy,
    related_item_candidate: str | None = None,
) -> ImageEvidenceRecord:
    consent = db.scalar(
        select(ConsentRecord)
        .where(ConsentRecord.user_id == user_id)
        .with_for_update()
    )
    if consent is None or not check_can_store(db, user_id, shopping_session_id):
        raise ConsentRequired("image storage requires an active consent grant")
    if RetentionPolicy(consent.retention_policy) != retention_policy:
        raise ConsentRequired("image retention must match the active consent choice")
    uri = store.put_image(image_bytes, content_type=content_type)
    active = capture_context == "while_shopping_query"
    record = ImageEvidenceRecord(
        user_id=user_id,
        capture_context=capture_context,
        processing_mode="active_then_background_enrichment" if active else "silent_background_enrichment",
        linked_shopping_session_id=shopping_session_id,
        related_item_candidate=related_item_candidate,
        storage_uri=uri,
        consent_status=consent.state,
        retention_policy=retention_policy,
        stored_for_future_enrichment=active and retention_policy != RetentionPolicy.delete_after_answer,
        retention_due_at=(
            datetime.now(timezone.utc) + timedelta(hours=1)
            if not active and retention_policy == RetentionPolicy.delete_after_enrichment
            else None
        ),
    )
    db.add(record)
    consume_single_image_grant(db, consent)
    db.commit()
    return record
