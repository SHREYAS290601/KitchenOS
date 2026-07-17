import uuid
from io import BytesIO

import pytest
from fastapi import UploadFile
from PIL import Image

from backend.app.models.consent import ConsentState, RetentionPolicy
from backend.app.models.image_evidence import ImageEvidenceRecord
from backend.app.services.consent import grant
from backend.app.services.image_storage import ConsentRequired, store_image
from backend.app.storage.local import LocalObjectStore
from backend.app.routes.images import ImageTooLarge, InvalidImage, read_validated_image


def make_image_bytes(size=(10, 10), image_format="JPEG"):
    output = BytesIO()
    Image.new("RGB", size, "red").save(output, format=image_format)
    return output.getvalue()


@pytest.mark.anyio
async def test_upload_validation_reencodes_a_real_image():
    upload = UploadFile(filename="photo.jpg", file=BytesIO(make_image_bytes()))

    data, content_type = await read_validated_image(upload, "image/jpeg")

    assert content_type == "image/jpeg"
    with Image.open(BytesIO(data)) as decoded:
        assert decoded.size == (10, 10)


@pytest.mark.anyio
async def test_upload_validation_rejects_spoofed_image_content():
    upload = UploadFile(filename="photo.jpg", file=BytesIO(b"not-an-image"))

    with pytest.raises(InvalidImage):
        await read_validated_image(upload, "image/jpeg")


@pytest.mark.anyio
async def test_upload_validation_enforces_streaming_byte_limit(monkeypatch):
    from backend.app.routes import images

    monkeypatch.setattr(images, "MAX_IMAGE_BYTES", 8)
    upload = UploadFile(filename="photo.jpg", file=BytesIO(b"123456789"))

    with pytest.raises(ImageTooLarge):
        await read_validated_image(upload, "image/jpeg")


@pytest.mark.anyio
async def test_upload_validation_rejects_dimensions_above_mobile_normalization_limit():
    upload = UploadFile(
        filename="too-wide.jpg",
        file=BytesIO(make_image_bytes(size=(4097, 1))),
    )

    with pytest.raises(ImageTooLarge):
        await read_validated_image(upload, "image/jpeg")


@pytest.mark.anyio
async def test_upload_rejects_oversized_header_before_pixel_decode(monkeypatch):
    from backend.app.routes import images

    class OversizedHeader:
        format = "JPEG"
        size = (4097, 4096)

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def load(self):
            raise AssertionError("pixel decode must not run for oversized headers")

    monkeypatch.setattr(images.Image, "open", lambda _stream: OversizedHeader())
    upload = UploadFile(filename="bomb.jpg", file=BytesIO(b"jpeg-header"))

    with pytest.raises(ImageTooLarge):
        await read_validated_image(upload, "image/jpeg")


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
    grant(
        db,
        user_id,
        ConsentState.granted_for_session,
        session_id="session-1",
        retention_policy=RetentionPolicy.delete_after_enrichment,
    )
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


def test_post_shopping_upload_gets_an_orphan_cleanup_deadline(db, tables, tmp_path):
    user_id = uuid.uuid4()
    grant(
        db,
        user_id,
        ConsentState.always_granted,
        retention_policy=RetentionPolicy.delete_after_enrichment,
    )

    record = store_image(
        db,
        LocalObjectStore(tmp_path),
        user_id=user_id,
        image_bytes=make_image_bytes(),
        content_type="image/jpeg",
        capture_context="post_shopping_check_in",
        shopping_session_id="session-1",
        retention_policy=RetentionPolicy.delete_after_enrichment,
    )

    assert record.retention_due_at is not None


def test_upload_cannot_expand_retention_beyond_the_consent_choice(db, tables, tmp_path):
    user_id = uuid.uuid4()
    grant(
        db,
        user_id,
        ConsentState.granted_for_session,
        session_id="session-1",
        retention_policy=RetentionPolicy.delete_after_enrichment,
    )

    with pytest.raises(ConsentRequired, match="retention"):
        store_image(
            db,
            LocalObjectStore(tmp_path),
            user_id=user_id,
            image_bytes=make_image_bytes(),
            content_type="image/jpeg",
            capture_context="post_shopping_check_in",
            shopping_session_id="session-1",
            retention_policy=RetentionPolicy.keep_for_pantry_memory,
        )

    assert list(tmp_path.iterdir()) == []
