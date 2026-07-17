import uuid

import pytest
from fastapi import HTTPException

from backend.app.deps import DevUser, _enforce_rate_limit


def test_database_rate_limit_is_independent_of_redis(db, tables, monkeypatch):
    monkeypatch.setenv("PANTRYOPS_REDIS_URL", "redis://127.0.0.1:1/0")
    user = DevUser(user_id=uuid.uuid4())

    _enforce_rate_limit(db, user, scope="test", limit=2, window_seconds=60)
    _enforce_rate_limit(db, user, scope="test", limit=2, window_seconds=60)

    with pytest.raises(HTTPException) as exc_info:
        _enforce_rate_limit(db, user, scope="test", limit=2, window_seconds=60)
    assert exc_info.value.status_code == 429
