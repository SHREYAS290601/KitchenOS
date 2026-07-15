import uuid

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
