import uuid

from pydantic import BaseModel

from backend.app.models.consent import ConsentState, RetentionPolicy


class ConsentUpdate(BaseModel):
    user_id: uuid.UUID = uuid.UUID("00000000-0000-0000-0000-000000000001")
    state: ConsentState
    shopping_session_id: str | None = None
    retention_policy: RetentionPolicy = RetentionPolicy.delete_after_answer


class ConsentResponse(BaseModel):
    user_id: uuid.UUID
    state: ConsentState
    shopping_session_id: str | None
    retention_policy: RetentionPolicy
