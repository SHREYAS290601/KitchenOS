from backend.app.config import Settings


def test_settings_read_from_env(monkeypatch):
    monkeypatch.setenv("PANTRYOPS_DATABASE_URL", "postgresql+psycopg://pantryops:pantryops@localhost:5432/pantryops")
    monkeypatch.setenv("PANTRYOPS_REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("PANTRYOPS_STORAGE_BACKEND", "minio")
    s = Settings()
    assert s.database_url.startswith("postgresql+psycopg://")
    assert s.storage_backend == "minio"
