import uuid
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from backend.app.models.consent import ConsentState
from backend.app.services.consent import (
    check_can_store,
    consume_single_image_grant,
    grant,
    revoke,
)


def test_consent_state_machine(db, tables):
    user_id = uuid.uuid4()
    row = grant(db, user_id, ConsentState.granted_for_single_image)
    assert check_can_store(db, user_id, None) is True
    consume_single_image_grant(db, row)
    assert check_can_store(db, user_id, None) is False

    grant(db, user_id, ConsentState.granted_for_session, session_id="session-a")
    assert check_can_store(db, user_id, "session-a") is True
    assert check_can_store(db, user_id, "session-b") is False

    grant(db, user_id, ConsentState.always_granted)
    assert check_can_store(db, user_id, "anything") is True
    revoke(db, user_id)
    assert check_can_store(db, user_id, "anything") is False


def test_default_consent_is_not_requested(db, tables):
    from backend.app.services.consent import get_state

    assert get_state(db, uuid.uuid4()).state == ConsentState.not_requested


def test_session_consent_expires(db, tables):
    user_id = uuid.uuid4()
    row = grant(db, user_id, ConsentState.granted_for_session, session_id="session-a")
    row.session_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()

    assert check_can_store(db, user_id, "session-a") is False


def test_consent_api_rejects_client_supplied_identity_or_session_id():
    from backend.app.schemas.consent import ConsentUpdate

    with pytest.raises(ValidationError):
        ConsentUpdate.model_validate(
            {
                "state": "granted_for_session",
                "shopping_session_id": "caller-controlled",
                "user_id": str(uuid.uuid4()),
            }
        )
