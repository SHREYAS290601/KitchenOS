import uuid
from datetime import datetime, timezone

from celery import chain

from backend.app.models.background_job import BackgroundJob, JobStatus
from backend.app.workers.celery_app import celery
from backend.app.workers.steps import (
    barcode_step,
    object_detection_step,
    ocr_step,
    product_enrichment_step,
    segmentation_step,
    worker_session,
)


@celery.task(name="pantryops.checkin.finalize")
def finalize_check_in(job_id: str) -> dict[str, str]:
    resolved_job_id = uuid.UUID(job_id)
    with worker_session() as session:
        job = session.get(BackgroundJob, resolved_job_id)
        if job is None:
            raise LookupError(f"background job {job_id} not found")
        if job.status == JobStatus.failed:
            return {"job_id": job_id, "status": JobStatus.failed.value}
        job.status = (
            JobStatus.completed if job.all_steps_completed() else JobStatus.needs_review
        )
        job.completed_at = datetime.now(timezone.utc)
        session.commit()
        return {"job_id": job_id, "status": str(job.status)}


def build_check_in_pipeline(job_id: str):
    return chain(
        segmentation_step.si(job_id),
        object_detection_step.si(job_id),
        ocr_step.si(job_id),
        barcode_step.si(job_id),
        product_enrichment_step.si(job_id),
        finalize_check_in.si(job_id),
    )


@celery.task(name="pantryops.checkin.run_pipeline")
def run_check_in_pipeline(job_id: str) -> dict[str, str]:
    resolved_job_id = uuid.UUID(job_id)
    with worker_session() as session:
        job = session.get(BackgroundJob, resolved_job_id)
        if job is None:
            raise LookupError(f"background job {job_id} not found")
        if job.status == JobStatus.completed:
            return {"job_id": job_id, "status": JobStatus.completed.value}
        if job.status == JobStatus.failed:
            return {"job_id": job_id, "status": JobStatus.failed.value}
        job.status = JobStatus.processing
        job.started_at = job.started_at or datetime.now(timezone.utc)
        session.commit()

    result = build_check_in_pipeline(job_id).apply_async()
    return {"job_id": job_id, "workflow_id": result.id}
