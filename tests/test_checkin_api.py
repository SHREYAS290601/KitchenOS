import uuid
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient

from backend.app.deps import get_current_user, get_db
from backend.app.main import create_app
from backend.app.models.background_job import BackgroundJob
from backend.app.models.consent import ConsentState, RetentionPolicy
from backend.app.models.image_evidence import ImageEvidenceRecord

USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
OTHER_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000002")


@dataclass(frozen=True)
class FakeUser:
    user_id: uuid.UUID = USER_ID


@pytest.fixture
def client(db, tables, monkeypatch, tmp_path):
    monkeypatch.setenv(
        "PANTRYOPS_DATABASE_URL",
        "postgresql+psycopg://pantryops:pantryops@localhost:5432/pantryops",
    )
    monkeypatch.setenv("PANTRYOPS_REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("PANTRYOPS_STORAGE_PATH", str(tmp_path))
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: FakeUser()
    return TestClient(app)


def add_image(
    db,
    *,
    user_id=USER_ID,
    session_id="session-001",
    consent_status=ConsentState.granted_for_session,
):
    image = ImageEvidenceRecord(
        user_id=user_id,
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


def check_in_payload(image_ids):
    return {
        "shopping_session_id": "session-001",
        "image_ids": [str(image_id) for image_id in image_ids],
        "processing_mode": "silent_background_enrichment",
    }


def test_checkin_creates_job_and_links_owned_images(client, db, monkeypatch):
    from backend.app.routes import checkin as checkin_route

    images = [add_image(db), add_image(db)]
    monkeypatch.setattr(checkin_route, "enqueue_check_in", lambda _job_id: None)

    response = client.post(
        "/check-in/groceries",
        json=check_in_payload([image.image_id for image in images]),
    )

    assert response.status_code == 202
    job = db.get(BackgroundJob, uuid.UUID(response.json()["job_id"]))
    assert job is not None
    assert job.image_ids == [str(image.image_id) for image in images]
    assert response.json()["steps"][0] == {
        "step": "image_storage",
        "status": "completed",
    }


def test_checkin_with_zero_images_returns_422(client):
    response = client.post("/check-in/groceries", json=check_in_payload([]))

    assert response.status_code == 422


def test_checkin_rejects_duplicate_images(client, db):
    image = add_image(db)

    response = client.post(
        "/check-in/groceries",
        json=check_in_payload([image.image_id, image.image_id]),
    )

    assert response.status_code == 422


@pytest.mark.parametrize("image_factory", ["missing", "foreign"])
def test_checkin_does_not_expose_missing_or_foreign_images(client, db, image_factory):
    image_id = (
        uuid.uuid4()
        if image_factory == "missing"
        else add_image(db, user_id=OTHER_USER_ID).image_id
    )

    response = client.post(
        "/check-in/groceries",
        json=check_in_payload([image_id]),
    )

    assert response.status_code == 404
    assert str(image_id) not in response.json()["detail"]


def test_enqueue_runs_only_after_job_commit(client, db, monkeypatch):
    from backend.app.routes import checkin as checkin_route

    image = add_image(db)
    transaction_states = []

    def observe_commit(_job_id):
        transaction_states.append(db.in_transaction())

    monkeypatch.setattr(checkin_route, "enqueue_check_in", observe_commit)
    response = client.post(
        "/check-in/groceries",
        json=check_in_payload([image.image_id]),
    )

    assert response.status_code == 202
    assert transaction_states == [False]


def test_enqueue_failure_leaves_committed_job_queued(client, db, monkeypatch):
    from backend.app.routes import checkin as checkin_route

    image = add_image(db)

    def fail_enqueue(_job_id):
        raise ConnectionError("broker unavailable")

    monkeypatch.setattr(checkin_route, "enqueue_check_in", fail_enqueue)
    response = client.post(
        "/check-in/groceries",
        json=check_in_payload([image.image_id]),
    )

    assert response.status_code == 202
    job = db.get(BackgroundJob, uuid.UUID(response.json()["job_id"]))
    assert job is not None
    assert job.status == "queued"
    assert job.dispatched_at is None
    assert job.dispatch_attempts == 1


def test_job_status_reads_durable_steps_and_is_user_scoped(client, db, monkeypatch):
    from backend.app.routes import checkin as checkin_route

    image = add_image(db)
    monkeypatch.setattr(checkin_route, "enqueue_check_in", lambda _job_id: None)
    created = client.post(
        "/check-in/groceries",
        json=check_in_payload([image.image_id]),
    )

    response = client.get(f"/jobs/{created.json()['job_id']}")

    assert response.status_code == 200
    assert response.json()["status"] == "queued"
    assert response.json()["steps"] == created.json()["steps"]

    job = db.get(BackgroundJob, uuid.UUID(created.json()["job_id"]))
    job.user_id = OTHER_USER_ID
    db.commit()
    assert client.get(f"/jobs/{job.job_id}").status_code == 404
