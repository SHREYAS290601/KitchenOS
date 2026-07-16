from backend.app.workers.celery_app import celery, make_celery


def test_celery_configured_from_settings(monkeypatch):
    monkeypatch.setenv(
        "PANTRYOPS_DATABASE_URL",
        "postgresql+psycopg://pantryops:pantryops@localhost:5432/pantryops",
    )
    monkeypatch.setenv("PANTRYOPS_REDIS_URL", "redis://localhost:6379/0")

    app = make_celery()

    assert app.conf.broker_url.startswith("redis://")
    assert app.conf.result_backend.startswith("redis://")
    assert app.conf.task_serializer == "json"


def test_eager_mode_runs_inline():
    celery.conf.task_always_eager = True

    @celery.task
    def add(a, b):
        return a + b

    assert add.delay(2, 3).get() == 5
