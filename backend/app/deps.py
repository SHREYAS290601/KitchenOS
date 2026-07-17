from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import secrets
import time
from typing import Iterator
import uuid

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from backend.app.models.api_rate_limit import ApiRateLimit


@dataclass(frozen=True)
class DevUser:
    user_id: uuid.UUID


_bearer = HTTPBearer(auto_error=False)


def get_db(request: Request) -> Iterator[Session]:
    session = request.app.state.session_factory()
    try:
        yield session
    finally:
        session.close()


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> DevUser:
    expected = request.app.state.settings.api_token.get_secret_value()
    if (
        credentials is None
        or credentials.scheme.lower() != "bearer"
        or not secrets.compare_digest(credentials.credentials, expected)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return DevUser(user_id=request.app.state.settings.user_id)


def _enforce_rate_limit(
    db: Session,
    user: DevUser,
    *,
    scope: str,
    limit: int,
    window_seconds: int,
) -> None:
    now = datetime.now(timezone.utc)
    bucket = int(time.time()) // window_seconds
    key = f"rate:{scope}:{user.user_id}:{bucket}"
    db.execute(delete(ApiRateLimit).where(ApiRateLimit.expires_at <= now))
    statement = (
        insert(ApiRateLimit)
        .values(
            bucket_key=key,
            count=1,
            expires_at=now + timedelta(seconds=window_seconds + 1),
        )
        .on_conflict_do_update(
            index_elements=[ApiRateLimit.bucket_key],
            set_={"count": ApiRateLimit.count + 1},
        )
        .returning(ApiRateLimit.count)
    )
    count = db.scalar(statement)
    db.commit()
    if count > limit:
        raise HTTPException(status_code=429, detail="rate limit exceeded")


def enforce_upload_rate_limit(
    user: DevUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    _enforce_rate_limit(
        db,
        user,
        scope="image_upload",
        limit=60,
        window_seconds=60,
    )


def enforce_checkin_rate_limit(
    user: DevUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    _enforce_rate_limit(
        db,
        user,
        scope="grocery_checkin",
        limit=30,
        window_seconds=60,
    )
