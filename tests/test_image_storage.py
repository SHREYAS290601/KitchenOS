import uuid

import pytest

from backend.app.models.consent import ConsentState, RetentionPolicy
from backend.app.models.image_evidence import ImageEvidenceRecord
from backend.app.services.consent import grant
from backend.app.services.image_storage import ConsentRequired, store_image
from backend.app.storage.local import LocalObjectStore


def test_store_image_requires_consent_before_touching_store(db, tables, tmp_path):
    store = LocalObjectStore(tmp_path)
    with pytest.raises(ConsentRequired):
        store_image(
            db,
            store,
            user_id=uuid.uuid4(),
            image_bytes=b"photo",
            content_type="image/jpeg",
            capture_context="while_shopping_query",
            shopping_session_id="session-1",
            retention_policy=RetentionPolicy.delete_after_answer,
        )
    assert list(tmp_path.iterdir()) == []
    assert db.query(ImageEvidenceRecord).count() == 0


def test_store_image_records_consent_and_active_reuse_linkage(db, tables, tmp_path):
    user_id = uuid.uuid4()
    grant(db, user_id, ConsentState.granted_for_session, session_id="session-1")
    record = store_image(
        db,
        LocalObjectStore(tmp_path),
        user_id=user_id,
        image_bytes=b"photo",
        content_type="image/jpeg",
        capture_context="while_shopping_query",
        shopping_session_id="session-1",
        retention_policy=RetentionPolicy.delete_after_enrichment,
        related_item_candidate="yogurt",
    )
    assert record.consent_status == ConsentState.granted_for_session
    assert record.processing_mode == "active_then_background_enrichment"
    assert record.stored_for_future_enrichment is True
    assert record.related_item_candidate == "yogurt"
    assert record.storage_uri.startswith("local://")
