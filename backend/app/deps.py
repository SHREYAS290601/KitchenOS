from dataclasses import dataclass
from typing import Iterator

from fastapi import Request
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class DevUser:
    user_id: str = "dev-user-001"


def get_db(request: Request) -> Iterator[Session]:
    session = request.app.state.session_factory()
    try:
        yield session
    finally:
        session.close()


def get_current_user() -> DevUser:
    return DevUser()
