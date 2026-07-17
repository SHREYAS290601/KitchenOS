import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from backend.app.deps import get_current_user, get_db
from backend.app.main import create_app
from backend.app.models.background_job import BackgroundJob
from backend.app.models.consent import ConsentRecord, ConsentState, RetentionPolicy
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
    consent = db.query(ConsentRecord).filter_by(user_id=user_id).one_or_none()
    if consent is None:
        db.add(
            ConsentRecord(
                user_id=user_id,
                state=consent_status,
                session_id=(
                    session_id
                    if consent_status == ConsentState.granted_for_session
                    else None
                ),
                session_expires_at=(
                    datetime.now(timezone.utc) + timedelta(hours=8)
                    if consent_status == ConsentState.granted_for_session
                    else None
                ),
                retention_policy=RetentionPolicy.delete_after_enrichment,
            )
        )
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
    assert job.dispatch_claimed_at is None


def test_pending_dispatch_retries_a_broker_failure(client, db, monkeypatch):
    from backend.app.routes import checkin as checkin_route
    from backend.app.services.checkin import dispatch_pending_jobs

    image = add_image(db)
    monkeypatch.setattr(
        checkin_route,
        "enqueue_check_in",
        lambda _job_id: (_ for _ in ()).throw(ConnectionError("broker unavailable")),
    )
    response = client.post(
        "/check-in/groceries",
        json=check_in_payload([image.image_id]),
    )
    job_id = uuid.UUID(response.json()["job_id"])
    dispatched = []

    assert dispatch_pending_jobs(db, lambda value: dispatched.append(value)) == 1
    db.expire_all()
    job = db.get(BackgroundJob, job_id)

    assert dispatched == [job_id]
    assert job.dispatched_at is not None
    assert job.dispatch_attempts == 2


def test_recent_dispatch_claim_prevents_duplicate_enqueue(db, tables):
    from backend.app.services.checkin import dispatch_background_job

    job = BackgroundJob(
        user_id=USER_ID,
        image_ids=[str(uuid.uuid4())],
        dispatch_claimed_at=datetime.now(timezone.utc),
    )
    db.add(job)
    db.commit()
    dispatched = []

    assert dispatch_background_job(db, job.job_id, dispatched.append) is False
    assert dispatched == []

    job.dispatch_claimed_at = datetime.now(timezone.utc) - timedelta(hours=1)
    db.commit()
    assert dispatch_background_job(db, job.job_id, dispatched.append) is True
    assert dispatched == [job.job_id]


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


def test_deleted_image_cannot_start_a_checkin(client, db):
    image = add_image(db)
    image.deleted_at = datetime.now(timezone.utc)
    db.commit()

    response = client.post(
        "/check-in/groceries",
        json=check_in_payload([image.image_id]),
    )

    assert response.status_code == 404


def test_mobile_check_in_agent_refuses_zero_images():
    from backend.app.agents.mobile_check_in import (
        MobileCheckInAgent,
        MobileCheckInContext,
    )

    agent = MobileCheckInAgent(lambda _context: uuid.uuid4())

    with pytest.raises(ValueError, match="user-provided images"):
        agent.run(
            MobileCheckInContext(
                user_id=USER_ID,
                shopping_session_id="session-001",
                image_ids=[],
            )
        )


def test_mobile_check_in_agent_returns_background_status_without_identity_claims():
    from backend.app.agents.mobile_check_in import (
        MobileCheckInAgent,
        MobileCheckInContext,
        MobileCheckInProposal,
    )

    expected_job_id = uuid.uuid4()
    context = MobileCheckInContext(
        user_id=USER_ID,
        shopping_session_id="session-001",
        image_ids=[uuid.uuid4()],
    )

    result = MobileCheckInAgent(lambda received: expected_job_id).run(context)

    assert result == MobileCheckInProposal(
        job_id=expected_job_id,
        status="processing_in_background",
    )
    assert "brand" not in MobileCheckInProposal.model_fields
    assert "product_name" not in MobileCheckInProposal.model_fields
