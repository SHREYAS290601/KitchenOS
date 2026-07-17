import os

from celery import Celery

from backend.app.config import Settings

_WORKER_IMPORTS = (
    "backend.app.workers.steps",
    "backend.app.workers.pipeline",
)
_BEAT_SCHEDULE = {
    "enforce-image-retention-hourly": {
        "task": "pantryops.retention.sweep",
        "schedule": 3600.0,
    },
    "dispatch-pending-check-ins": {
        "task": "pantryops.checkin.dispatch_pending",
        "schedule": 30.0,
    },
}


def _configure(app: Celery, redis_url: str) -> Celery:
    app.conf.update(
        broker_url=redis_url,
        result_backend=redis_url,
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        enable_utc=True,
        imports=_WORKER_IMPORTS,
        beat_schedule={key: dict(value) for key, value in _BEAT_SCHEDULE.items()},
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        task_publish_retry=True,
        worker_prefetch_multiplier=1,
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
