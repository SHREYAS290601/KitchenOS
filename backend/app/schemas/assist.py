import uuid

from pydantic import BaseModel

from backend.app.agents.auditor import AuditVerdict


class AssistRequest(BaseModel):
    question: str
    image_id: uuid.UUID | None = None
    shopping_session_id: str | None = None
    user_id: uuid.UUID = uuid.UUID("00000000-0000-0000-0000-000000000001")


class AssistResponse(BaseModel):
    answer: str
    applied_preference_ids: list[str]
    audit: AuditVerdict
    degraded: bool
    image_id: uuid.UUID | None = None
