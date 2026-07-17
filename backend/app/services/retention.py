import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.background_job import BackgroundJob, JobStatus
from backend.app.models.consent import RetentionPolicy
from backend.app.models.image_evidence import ImageEvidenceRecord
from backend.app.storage.base import ObjectStore
from backend.app.storage.local import ObjectNotFound

_TERMINAL_JOB_STATUSES = {
    JobStatus.completed,
    JobStatus.failed,
    JobStatus.needs_review,
}


def mark_retention_due(db: Session, image: ImageEvidenceRecord) -> None:
    image.retention_due_at = datetime.now(timezone.utc)
    db.add(image)
    db.commit()


def _delete_images(
    db: Session,
    store: ObjectStore,
    images: list[ImageEvidenceRecord],
) -> int:
    deleted = 0
    now = datetime.now(timezone.utc)
    for image in images:
        if image.deleted_at is not None:
            continue
        try:
            store.delete(image.storage_uri)
        except ObjectNotFound:
            pass
        image.deleted_at = now
        image.stored_for_future_enrichment = False
        db.add(image)
        deleted += 1
    db.commit()
    return deleted


def enforce_retention_for_job(
    db: Session,
    store: ObjectStore,
    job_id: uuid.UUID,
) -> int:
    job = db.get(BackgroundJob, job_id)
    if (
        job is None
        or JobStatus(job.status) not in _TERMINAL_JOB_STATUSES
        or job.retention_enforced_at is not None
    ):
        return 0
    image_ids = [uuid.UUID(image_id) for image_id in job.image_ids]
    images = list(
        db.scalars(
            select(ImageEvidenceRecord).where(
                ImageEvidenceRecord.image_id.in_(image_ids),
                ImageEvidenceRecord.retention_policy
                == RetentionPolicy.delete_after_enrichment,
                ImageEvidenceRecord.deleted_at.is_(None),
            )
        )
    )
    deleted = _delete_images(db, store, images)
    job = db.get(BackgroundJob, job_id)
    if job is not None:
        job.retention_enforced_at = datetime.now(timezone.utc)
        db.commit()
    return deleted


def sweep_retention(db: Session, store: ObjectStore) -> int:
    now = datetime.now(timezone.utc)
    due_after_answer = list(
        db.scalars(
            select(ImageEvidenceRecord).where(
                ImageEvidenceRecord.retention_policy
                == RetentionPolicy.delete_after_answer,
                ImageEvidenceRecord.retention_due_at.is_not(None),
                ImageEvidenceRecord.retention_due_at <= now,
                ImageEvidenceRecord.deleted_at.is_(None),
            )
        )
    )
    referenced_ids = {
        uuid.UUID(image_id)
        for image_ids in db.scalars(select(BackgroundJob.image_ids))
        for image_id in image_ids
    }
    due_orphans = [
        image
        for image in db.scalars(
            select(ImageEvidenceRecord).where(
                ImageEvidenceRecord.retention_policy
                == RetentionPolicy.delete_after_enrichment,
                ImageEvidenceRecord.retention_due_at.is_not(None),
                ImageEvidenceRecord.retention_due_at <= now,
                ImageEvidenceRecord.deleted_at.is_(None),
            )
        )
        if image.image_id not in referenced_ids
    ]
    deleted = _delete_images(db, store, due_after_answer + due_orphans)
    terminal_jobs = list(
        db.scalars(
            select(BackgroundJob).where(
                BackgroundJob.status.in_(_TERMINAL_JOB_STATUSES),
                BackgroundJob.retention_enforced_at.is_(None),
            )
        )
    )
    return deleted + sum(
        enforce_retention_for_job(db, store, job.job_id) for job in terminal_jobs
    )
