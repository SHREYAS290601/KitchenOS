import uuid
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class CheckInRequest(BaseModel):
    shopping_session_id: str = Field(min_length=1, max_length=200)
    image_ids: list[uuid.UUID] = Field(min_length=1, max_length=20)
    processing_mode: Literal["silent_background_enrichment"]

    @field_validator("image_ids")
    @classmethod
    def image_ids_must_be_unique(cls, image_ids: list[uuid.UUID]) -> list[uuid.UUID]:
        if len(image_ids) != len(set(image_ids)):
            raise ValueError("image_ids must not contain duplicates")
        return list(image_ids)


class JobStepOut(BaseModel):
    step: str
    status: str


class CheckInResponse(BaseModel):
    job_id: uuid.UUID
    status: str
    steps: list[JobStepOut]


class JobStatusOut(CheckInResponse):
    job_type: str
    image_ids: list[str]
    created_at: str
    completed_at: str | None = None
    error: str | None = None
