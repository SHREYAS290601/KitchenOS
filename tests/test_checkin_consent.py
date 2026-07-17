import uuid
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient

from backend.app.deps import get_current_user, get_db
from backend.app.main import create_app
from backend.app.models.consent import ConsentRecord, ConsentState, RetentionPolicy
from backend.app.models.image_evidence import ImageEvidenceRecord

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
