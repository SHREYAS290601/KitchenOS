from pydantic import BaseModel, ConfigDict

from backend.app.models.consent import ConsentState, RetentionPolicy


class ConsentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: ConsentState
    retention_policy: RetentionPolicy = RetentionPolicy.delete_after_answer


class ConsentResponse(BaseModel):
    user_id: str
    state: ConsentState
    shopping_session_id: str | None
    retention_policy: RetentionPolicy
