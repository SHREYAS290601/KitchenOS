import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.config import Settings
from backend.app.db import make_engine, make_session_factory
from backend.app.models.background_job import BackgroundJob, JobStatus, StepStatus
from backend.app.models.image_evidence import ImageEvidenceRecord
from backend.app.services.checkin import consent_allows_processing
from backend.app.workers.celery_app import celery


class ConsentRevokedError(PermissionError):
    pass


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


def _mark_failed(job_id: uuid.UUID, step_name: str, error: Exception) -> None:
    with worker_session() as session:
        job = _load_job(session, job_id)
        job.set_step_status(step_name, StepStatus.failed)
        job.status = JobStatus.failed
        job.error = str(error)[:500]
        job.completed_at = datetime.now(timezone.utc)
        session.commit()


def run_stub(step_name: str, job_id: uuid.UUID) -> dict:
    """Phase 5 placeholder; Phase 6 replaces these typed empty bodies."""
    return _result(job_id, step_name)


def execute_job_step(job_id: str, step_name: str) -> dict:
    resolved_job_id = uuid.UUID(job_id)
    try:
        with worker_session() as session:
            job = _load_job(session, resolved_job_id)
            if _step_status(job, step_name) == StepStatus.completed:
                return _result(resolved_job_id, step_name)
            _assert_current_consent(session, job)
            job.status = JobStatus.processing
            job.started_at = job.started_at or datetime.now(timezone.utc)
            job.set_step_status(step_name, StepStatus.processing)
            session.commit()

        result = run_stub(step_name, resolved_job_id)

        with worker_session() as session:
            job = _load_job(session, resolved_job_id)
            _assert_current_consent(session, job)
            job.set_step_status(step_name, StepStatus.completed)
            job.error = None
            session.commit()
        return result
    except Exception as exc:
        _mark_failed(resolved_job_id, step_name, exc)
        raise


@celery.task(name="pantryops.checkin.segmentation")
def segmentation_step(job_id: str) -> dict:
    return execute_job_step(job_id, "segmentation")


@celery.task(name="pantryops.checkin.object_detection")
def object_detection_step(job_id: str) -> dict:
    return execute_job_step(job_id, "object_detection")


@celery.task(name="pantryops.checkin.ocr")
def ocr_step(job_id: str) -> dict:
    return execute_job_step(job_id, "ocr")


@celery.task(name="pantryops.checkin.barcode")
def barcode_step(job_id: str) -> dict:
    return execute_job_step(job_id, "barcode")


@celery.task(name="pantryops.checkin.product_enrichment")
def product_enrichment_step(job_id: str) -> dict:
    return execute_job_step(job_id, "product_enrichment")
