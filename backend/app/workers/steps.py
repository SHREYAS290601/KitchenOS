import logging
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.config import Settings
from backend.app.db import make_engine, make_session_factory
from backend.app.models.background_job import BackgroundJob, JobStatus, StepStatus
from backend.app.models.image_evidence import ImageEvidenceRecord
from backend.app.services.checkin import consent_allows_processing
from backend.app.workers.celery_app import celery

logger = logging.getLogger(__name__)

class ConsentRevokedError(PermissionError):
    pass


_TRANSIENT_STEP_ERRORS = (SQLAlchemyError, ConnectionError, TimeoutError, OSError)


@contextmanager
def worker_session() -> Iterator[Session]:
    settings = Settings()
    engine = make_engine(settings.database_url)
    session = make_session_factory(engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@contextmanager
def locked_step_session(job_id: uuid.UUID, step_name: str) -> Iterator[Session]:
    """Serialize duplicate deliveries while allowing crash recovery.

    PostgreSQL session-level advisory locks are released automatically if a
    worker process loses its database connection.
    """
    settings = Settings()
    engine = make_engine(settings.database_url)
    connection = engine.connect()
    session = Session(bind=connection, expire_on_commit=False)
    lock_key = f"pantryops:{job_id}:{step_name}"
    try:
        session.execute(
            text("SELECT pg_advisory_lock(hashtextextended(:key, 0))"),
            {"key": lock_key},
        )
        yield session
    finally:
        session.rollback()
        session.execute(
            text("SELECT pg_advisory_unlock(hashtextextended(:key, 0))"),
            {"key": lock_key},
        )
        session.commit()
        session.close()
        connection.close()
        engine.dispose()


def _load_job(session: Session, job_id: uuid.UUID) -> BackgroundJob:
    job = session.get(BackgroundJob, job_id)
    if job is None:
        raise LookupError(f"background job {job_id} not found")
    return job


def _step_status(job: BackgroundJob, step_name: str) -> str:
    return next(
        step["status"] for step in job.steps if step["step"] == step_name
    )


def _assert_current_consent(session: Session, job: BackgroundJob) -> None:
    image_ids = [uuid.UUID(image_id) for image_id in job.image_ids]
    images = list(
        session.scalars(
            select(ImageEvidenceRecord).where(
                ImageEvidenceRecord.image_id.in_(image_ids),
                ImageEvidenceRecord.user_id == job.user_id,
            )
        )
    )
    if len(images) != len(image_ids) or any(
        not consent_allows_processing(session, image) for image in images
    ):
        raise ConsentRevokedError("consent no longer allows silent processing")


def _result(job_id: uuid.UUID, step_name: str) -> dict:
    return {"job_id": str(job_id), "step": step_name, "candidates": []}


def _log_step_failure(job_id: uuid.UUID, step_name: str, error: Exception) -> None:
    logger.error(
        "check-in step failed",
        exc_info=(type(error), error, error.__traceback__),
        extra={"job_id": str(job_id), "step": step_name},
    )


def _persist_failure(
    session: Session,
    job_id: uuid.UUID,
    step_name: str,
    error: Exception,
) -> bool:
    job = _load_job(session, job_id)
    if (
        _step_status(job, step_name) == StepStatus.completed
        or job.status in {JobStatus.completed, JobStatus.failed, JobStatus.needs_review}
    ):
        return False
    job.set_step_status(step_name, StepStatus.failed)
    job.status = JobStatus.failed
    job.error = (
        "consent_revoked"
        if isinstance(error, ConsentRevokedError)
        else "processing_failed"
    )
    job.completed_at = datetime.now(timezone.utc)
    session.commit()
    return True


def _enqueue_failure_retention(job_id: uuid.UUID) -> None:
    try:
        from backend.app.workers.pipeline import enforce_retention

        enforce_retention.apply_async(
            args=[str(job_id)],
            task_id=f"retention-failure-{job_id}",
        )
    except Exception:
        logger.exception(
            "failed to enqueue immediate retention; beat will reconcile",
            extra={"job_id": str(job_id)},
        )


def _mark_failed(job_id: uuid.UUID, step_name: str, error: Exception) -> None:
    """Conditionally fail a step while holding its duplicate-delivery lock."""
    _log_step_failure(job_id, step_name, error)
    with locked_step_session(job_id, step_name) as session:
        changed = _persist_failure(session, job_id, step_name, error)
    if changed:
        _enqueue_failure_retention(job_id)


def run_stub(step_name: str, job_id: uuid.UUID) -> dict:
    """Phase 5 placeholder; Phase 6 replaces these typed empty bodies."""
    return _result(job_id, step_name)


def execute_job_step(job_id: str, step_name: str) -> dict:
    resolved_job_id = uuid.UUID(job_id)
    with locked_step_session(resolved_job_id, step_name) as session:
        try:
            job = _load_job(session, resolved_job_id)
            if _step_status(job, step_name) == StepStatus.completed:
                return _result(resolved_job_id, step_name)
            if job.status in {
                JobStatus.completed,
                JobStatus.failed,
                JobStatus.needs_review,
            }:
                return _result(resolved_job_id, step_name)
            _assert_current_consent(session, job)
            job.status = JobStatus.processing
            job.started_at = job.started_at or datetime.now(timezone.utc)
            job.set_step_status(step_name, StepStatus.processing)
            session.commit()

            result = run_stub(step_name, resolved_job_id)

            job = _load_job(session, resolved_job_id)
            _assert_current_consent(session, job)
            job.set_step_status(step_name, StepStatus.completed)
            job.error = None
            session.commit()
            return result
        except ConsentRevokedError as exc:
            _log_step_failure(resolved_job_id, step_name, exc)
            if _persist_failure(session, resolved_job_id, step_name, exc):
                _enqueue_failure_retention(resolved_job_id)
            raise
        except _TRANSIENT_STEP_ERRORS:
            raise
        except Exception as exc:
            _log_step_failure(resolved_job_id, step_name, exc)
            if _persist_failure(session, resolved_job_id, step_name, exc):
                _enqueue_failure_retention(resolved_job_id)
            raise


def _execute_with_retry(task, job_id: str, step_name: str) -> dict:
    try:
        return execute_job_step(job_id, step_name)
    except ConsentRevokedError:
        raise
    except _TRANSIENT_STEP_ERRORS as exc:
        if task.request.retries >= task.max_retries:
            _mark_failed(uuid.UUID(job_id), step_name, exc)
            raise
        raise task.retry(exc=exc, countdown=min(2 ** task.request.retries, 30))


@celery.task(bind=True, max_retries=3, name="pantryops.checkin.segmentation")
def segmentation_step(self, job_id: str) -> dict:
    return _execute_with_retry(self, job_id, "segmentation")


@celery.task(bind=True, max_retries=3, name="pantryops.checkin.object_detection")
def object_detection_step(self, job_id: str) -> dict:
    return _execute_with_retry(self, job_id, "object_detection")


@celery.task(bind=True, max_retries=3, name="pantryops.checkin.ocr")
def ocr_step(self, job_id: str) -> dict:
    return _execute_with_retry(self, job_id, "ocr")


@celery.task(bind=True, max_retries=3, name="pantryops.checkin.barcode")
def barcode_step(self, job_id: str) -> dict:
    return _execute_with_retry(self, job_id, "barcode")


@celery.task(bind=True, max_retries=3, name="pantryops.checkin.product_enrichment")
def product_enrichment_step(self, job_id: str) -> dict:
    return _execute_with_retry(self, job_id, "product_enrichment")
