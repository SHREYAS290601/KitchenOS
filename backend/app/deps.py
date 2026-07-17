from dataclasses import dataclass
from typing import Iterator
import uuid

from fastapi import Request
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class DevUser:
    user_id: uuid.UUID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def get_db(request: Request) -> Iterator[Session]:
    session = request.app.state.session_factory()
    try:
        yield session
    finally:
        session.close()


def get_current_user() -> DevUser:
    return DevUser()
