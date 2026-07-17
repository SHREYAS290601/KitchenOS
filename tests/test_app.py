import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv(
        "PANTRYOPS_DATABASE_URL",
        "postgresql+psycopg://pantryops:pantryops@localhost:5432/pantryops",
    )
    monkeypatch.setenv("PANTRYOPS_REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("PANTRYOPS_API_TOKEN", "test-api-token-with-minimum-32-chars")
    return TestClient(create_app())


@pytest.fixture
def client_bad_db(monkeypatch):
    monkeypatch.setenv(
        "PANTRYOPS_DATABASE_URL",
        "postgresql+psycopg://pantryops:pantryops@localhost:59999/pantryops",
    )
    monkeypatch.setenv("PANTRYOPS_REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("PANTRYOPS_API_TOKEN", "test-api-token-with-minimum-32-chars")
    return TestClient(create_app())


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "service": "pantryops"}


def test_readyz_ok(client):
    assert client.get("/readyz").status_code == 200


def test_readyz_503_when_db_unreachable(client_bad_db):
    assert client_bad_db.get("/readyz").status_code == 503


@pytest.fixture
def app_with_probe_route(monkeypatch):
    from fastapi import Depends

    from backend.app.deps import get_current_user, get_db

    monkeypatch.setenv(
        "PANTRYOPS_DATABASE_URL",
        "postgresql+psycopg://pantryops:pantryops@localhost:5432/pantryops",
    )
    monkeypatch.setenv("PANTRYOPS_REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("PANTRYOPS_API_TOKEN", "test-api-token-with-minimum-32-chars")
    app = create_app()

    @app.get("/_probe")
    def probe(db=Depends(get_db), user=Depends(get_current_user)):
        return {"user_id": user.user_id, "db_open": db.is_active}

    return app


def test_get_current_user_requires_valid_bearer_token(app_with_probe_route):
    client = TestClient(app_with_probe_route)
    assert client.get("/_probe").status_code == 401
    assert client.get(
        "/_probe",
        headers={"Authorization": "Bearer wrong-token"},
    ).status_code == 401


def test_get_current_user_returns_authenticated_user(app_with_probe_route):
    r = TestClient(app_with_probe_route).get(
        "/_probe",
        headers={"Authorization": "Bearer test-api-token-with-minimum-32-chars"},
    )
    assert r.status_code == 200
    assert r.json() == {
        "user_id": "00000000-0000-0000-0000-000000000001",
        "db_open": True,
    }


def test_dependencies_can_be_overridden(app_with_probe_route):
    from backend.app.deps import get_current_user

    class FakeUser:
        user_id = "override-user"

    app_with_probe_route.dependency_overrides[get_current_user] = lambda: FakeUser()
    r = TestClient(app_with_probe_route).get("/_probe")
    assert r.json()["user_id"] == "override-user"


def test_sensitive_routes_reject_unauthenticated_requests(client):
    requests = [
        client.post(
            "/consent",
            json={"state": "always_granted", "retention_policy": "keep_for_pantry_memory"},
        ),
        client.get("/pantry/items"),
        client.post("/shopping-lists", json={"goal": "weekly groceries"}),
        client.post("/consumption/ad-hoc", json={"message": "I used milk"}),
    ]

    assert [response.status_code for response in requests] == [401, 401, 401, 401]
