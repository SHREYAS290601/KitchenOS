import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from backend.app.deps import get_current_user, get_db
from backend.app.main import create_app
from backend.app.models.background_job import BackgroundJob, JobStatus, initial_check_in_steps
from backend.app.models.consent import ConsentRecord, ConsentState, RetentionPolicy
from backend.app.models.image_evidence import ImageEvidenceRecord
from backend.app.services.retention import enforce_retention_for_job, sweep_retention
from backend.app.storage.local import LocalObjectStore, ObjectNotFound

USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


@dataclass(frozen=True)
class FakeUser:
    user_id: uuid.UUID = USER_ID


@pytest.fixture
def client(db, tables, monkeypatch, tmp_path):
    from backend.app.routes import checkin as checkin_route

    monkeypatch.setenv(
        "PANTRYOPS_DATABASE_URL",
        "postgresql+psycopg://pantryops:pantryops@localhost:5432/pantryops",
    )
    monkeypatch.setenv("PANTRYOPS_REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("PANTRYOPS_STORAGE_PATH", str(tmp_path))
    monkeypatch.setattr(checkin_route, "enqueue_check_in", lambda _job_id: None)
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: FakeUser()
    return TestClient(app)


def add_consent(db, state: ConsentState, *, session_id="session-001"):
    row = ConsentRecord(
        user_id=USER_ID,
        state=state,
        session_id=session_id if state == ConsentState.granted_for_session else None,
        session_expires_at=(
            datetime.now(timezone.utc) + timedelta(hours=8)
            if state == ConsentState.granted_for_session
            else None
        ),
        retention_policy=RetentionPolicy.delete_after_enrichment,
    )
    db.add(row)
    db.commit()
    return row


def add_image(db, consent_status: ConsentState, *, session_id="session-001"):
    image = ImageEvidenceRecord(
        user_id=USER_ID,
        capture_context="post_shopping_check_in",
        processing_mode="silent_background_enrichment",
        linked_shopping_session_id=session_id,
        storage_uri=f"local://{uuid.uuid4()}.jpg",
        consent_status=consent_status,
        retention_policy=RetentionPolicy.delete_after_enrichment,
        stored_for_future_enrichment=True,
    )
    db.add(image)
    db.commit()
    return image


def payload(image_id, *, session_id="session-001"):
    return {
        "shopping_session_id": session_id,
        "image_ids": [str(image_id)],
        "processing_mode": "silent_background_enrichment",
    }


@pytest.mark.parametrize(
    "state",
    [
        ConsentState.denied,
        ConsentState.not_requested,
        ConsentState.revoked,
        ConsentState.granted_for_single_image,
    ],
)
def test_checkin_rejects_consent_not_valid_for_silent_processing(client, db, state):
    if state != ConsentState.not_requested:
        add_consent(db, state)
    image = add_image(db, state)

    response = client.post("/check-in/groceries", json=payload(image.image_id))

    assert response.status_code == 403
    assert str(image.image_id) in response.json()["detail"]


@pytest.mark.parametrize(
    "state",
    [ConsentState.granted_for_session, ConsentState.always_granted],
)
def test_checkin_accepts_session_or_always_consent(client, db, state):
    add_consent(db, state)
    image = add_image(db, state)

    response = client.post("/check-in/groceries", json=payload(image.image_id))

    assert response.status_code == 202


def test_session_consent_must_match_checkin_session(client, db):
    add_consent(db, ConsentState.granted_for_session, session_id="session-other")
    image = add_image(db, ConsentState.granted_for_session)

    response = client.post("/check-in/groceries", json=payload(image.image_id))

    assert response.status_code == 403
    assert str(image.image_id) in response.json()["detail"]


def test_shared_worker_predicate_detects_revocation(db, tables):
    from backend.app.services.checkin import consent_allows_processing

    consent = add_consent(db, ConsentState.granted_for_session)
    image = add_image(db, ConsentState.granted_for_session)
    assert consent_allows_processing(db, image) is True

    consent.state = ConsentState.revoked
    consent.session_id = None
    db.commit()

    assert consent_allows_processing(db, image) is False


def add_retention_job(db, store, policy, *, status=JobStatus.completed):
    user_id = uuid.uuid4()
    image = ImageEvidenceRecord(
        user_id=user_id,
        capture_context="post_shopping_check_in",
        processing_mode="silent_background_enrichment",
        linked_shopping_session_id="session-001",
        storage_uri=store.put_image(b"photo", content_type="image/jpeg"),
        consent_status=ConsentState.always_granted,
        retention_policy=policy,
        stored_for_future_enrichment=True,
    )
    db.add(image)
    db.flush()
    job = BackgroundJob(
        status=status,
        user_id=user_id,
        image_ids=[str(image.image_id)],
        steps=initial_check_in_steps(),
    )
    db.add(job)
    db.commit()
    return job, image


def test_completed_job_deletes_enrichment_image_and_marks_row(db, tables, tmp_path):
    store = LocalObjectStore(tmp_path)
    job, image = add_retention_job(
        db,
        store,
        RetentionPolicy.delete_after_enrichment,
    )

    assert enforce_retention_for_job(db, store, job.job_id) == 1
    db.refresh(image)

    assert image.deleted_at is not None
    with pytest.raises(ObjectNotFound):
        store.open(image.storage_uri)


def test_incomplete_job_does_not_delete_enrichment_image(db, tables, tmp_path):
    store = LocalObjectStore(tmp_path)
    job, image = add_retention_job(
        db,
        store,
        RetentionPolicy.delete_after_enrichment,
        status=JobStatus.processing,
    )

    assert enforce_retention_for_job(db, store, job.job_id) == 0
    db.refresh(image)
    assert image.deleted_at is None
    assert store.open(image.storage_uri) == b"photo"


def test_keep_for_pantry_memory_survives_retention(db, tables, tmp_path):
    store = LocalObjectStore(tmp_path)
    job, image = add_retention_job(
        db,
        store,
        RetentionPolicy.keep_for_pantry_memory,
    )

    assert enforce_retention_for_job(db, store, job.job_id) == 0
    assert store.open(image.storage_uri) == b"photo"


def test_due_delete_after_answer_image_is_swept_idempotently(db, tables, tmp_path):
    store = LocalObjectStore(tmp_path)
    user_id = uuid.uuid4()
    image = ImageEvidenceRecord(
        user_id=user_id,
        capture_context="while_shopping_query",
        processing_mode="active_then_background_enrichment",
        storage_uri="local://already-missing.jpg",
        consent_status=ConsentState.granted_for_single_image,
        retention_policy=RetentionPolicy.delete_after_answer,
        stored_for_future_enrichment=False,
        retention_due_at=datetime.now(timezone.utc),
    )
    db.add(image)
    db.commit()

    assert sweep_retention(db, store) == 1
    db.refresh(image)
    assert image.deleted_at is not None
    assert sweep_retention(db, store) == 0


def test_due_orphaned_checkin_upload_is_swept(db, tables, tmp_path):
    store = LocalObjectStore(tmp_path)
    image = ImageEvidenceRecord(
        user_id=uuid.uuid4(),
        capture_context="post_shopping_check_in",
        processing_mode="silent_background_enrichment",
        linked_shopping_session_id="abandoned-session",
        storage_uri=store.put_image(b"photo", content_type="image/jpeg"),
        consent_status=ConsentState.granted_for_session,
        retention_policy=RetentionPolicy.delete_after_enrichment,
        stored_for_future_enrichment=True,
        retention_due_at=datetime.now(timezone.utc),
    )
    db.add(image)
    db.commit()

    assert sweep_retention(db, store) == 1
    db.refresh(image)
    assert image.deleted_at is not None


def test_retention_task_is_registered_with_celery_beat():
    from backend.app.workers.celery_app import celery
    from backend.app.workers import pipeline  # noqa: F401

    schedule = celery.conf.beat_schedule["enforce-image-retention-hourly"]
    assert schedule["task"] == "pantryops.retention.sweep"
