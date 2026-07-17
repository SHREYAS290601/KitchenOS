import uuid
from collections.abc import Callable
from typing import Literal

from pydantic import BaseModel, ConfigDict


class MobileCheckInContext(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: uuid.UUID
    shopping_session_id: str
    image_ids: tuple[uuid.UUID, ...]


class MobileCheckInProposal(BaseModel):
    model_config = ConfigDict(frozen=True)

    job_id: uuid.UUID
    status: Literal["processing_in_background"] = "processing_in_background"


class MobileCheckInAgent:
    """Typed orchestration shell; the injected service owns persistence."""

    def __init__(self, start_check_in: Callable[[MobileCheckInContext], uuid.UUID]):
        self._start_check_in = start_check_in

    def run(self, context: MobileCheckInContext) -> MobileCheckInProposal:
        if not context.image_ids:
            raise ValueError("must not run without user-provided images")
        return MobileCheckInProposal(job_id=self._start_check_in(context))
