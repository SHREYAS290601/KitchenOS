import os

from celery import Celery

from backend.app.config import Settings


def _configure(app: Celery, redis_url: str) -> Celery:
    app.conf.update(
        broker_url=redis_url,
        result_backend=redis_url,
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        enable_utc=True,
    )
    return app


def make_celery(settings: Settings | None = None) -> Celery:
    """Build the worker app from validated application settings."""
    resolved_settings = settings or Settings()
    return _configure(Celery("pantryops"), resolved_settings.redis_url)


# Keep imports safe for CLI/test discovery before the full application settings
# are present. Runtime entrypoints call make_celery() with validated Settings.
celery = _configure(
    Celery("pantryops"),
    os.environ.get("PANTRYOPS_REDIS_URL", "redis://localhost:6379/0"),
)
