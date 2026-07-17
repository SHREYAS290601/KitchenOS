import logging
import uuid
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from backend.app.models.background_job import BackgroundJob, JobStatus, initial_check_in_steps
from backend.app.models.consent import ConsentRecord, ConsentState
from backend.app.models.image_evidence import ImageEvidenceRecord
from backend.app.schemas.checkin import CheckInRequest

logger = logging.getLogger(__name__)
_DISPATCH_LEASE = timedelta(minutes=15)


class CheckInImagesNotFound(LookupError):
    pass


class InvalidCheckInImages(ValueError):
    pass


class CheckInConsentRequired(PermissionError):
    def __init__(self, image_id: uuid.UUID):
        self.image_id = image_id
        super().__init__(f"image {image_id} is not consented for silent processing")


_SILENT_CONSENT_STATES = {
    ConsentState.granted_for_session,
    ConsentState.always_granted,
}


def consent_allows_processing(db: Session, image: ImageEvidenceRecord) -> bool:
    """Check both the upload-time snapshot and current revocable consent."""
    try:
        image_state = ConsentState(image.consent_status)
    except ValueError:
        return False
    if image_state not in _SILENT_CONSENT_STATES:
        return False

    current = db.scalar(
        select(ConsentRecord).where(ConsentRecord.user_id == image.user_id)
    )
    if current is None:
        return False
    try:
        current_state = ConsentState(current.state)
    except ValueError:
        return False
    if current_state not in _SILENT_CONSENT_STATES:
        return False
    if current_state == ConsentState.granted_for_session:
        return bool(
            current.session_id
            and current.session_id == image.linked_shopping_session_id
            and current.session_expires_at
            and current.session_expires_at > datetime.now(timezone.utc)
        )
    return True


def _load_owned_images(
    db: Session,
    *,
    user_id: uuid.UUID,
    image_ids: list[uuid.UUID],
) -> list[ImageEvidenceRecord]:
    images = list(
        db.scalars(
            select(ImageEvidenceRecord).where(
                ImageEvidenceRecord.image_id.in_(image_ids),
                ImageEvidenceRecord.user_id == user_id,
                ImageEvidenceRecord.deleted_at.is_(None),
            )
        )
    )
    if len(images) != len(image_ids):
        raise CheckInImagesNotFound("one or more images were not found")
    by_id = {image.image_id: image for image in images}
    return [by_id[image_id] for image_id in image_ids]


def create_check_in(
    db: Session,
    *,
    user_id: uuid.UUID,
    request: CheckInRequest,
) -> BackgroundJob:
    images = _load_owned_images(db, user_id=user_id, image_ids=request.image_ids)
    invalid = [
        image
        for image in images
        if image.capture_context != "post_shopping_check_in"
        or image.processing_mode != request.processing_mode
        or image.linked_shopping_session_id != request.shopping_session_id
    ]
    if invalid:
        raise InvalidCheckInImages(
            "all images must be post-shopping uploads linked to this shopping session"
        )

    for image in images:
        if not consent_allows_processing(db, image):
            raise CheckInConsentRequired(image.image_id)

    job = BackgroundJob(
        job_type="grocery_image_check_in",
        status=JobStatus.queued,
        user_id=user_id,
        image_ids=[str(image_id) for image_id in request.image_ids],
        steps=initial_check_in_steps(),
    )
    db.add(job)
    db.flush()
    return job


def enqueue_check_in(job_id: uuid.UUID) -> None:
    """Publish the real chain so there is no launcher-to-chain crash window."""
    from backend.app.workers.pipeline import build_check_in_pipeline

    build_check_in_pipeline(str(job_id)).apply_async(
        task_id=f"check-in-{job_id}",
    )


def dispatch_background_job(
    db: Session,
    job_id: uuid.UUID,
    enqueue: Callable[[uuid.UUID], None] = enqueue_check_in,
) -> bool:
    now = datetime.now(timezone.utc)
    claim_cutoff = now - _DISPATCH_LEASE
    job = db.scalar(
        select(BackgroundJob)
        .where(BackgroundJob.job_id == job_id)
        .with_for_update()
    )
    if job is None:
        return False
    if job.dispatched_at is not None:
        return True
    if job.dispatch_claimed_at is not None and job.dispatch_claimed_at > claim_cutoff:
        db.rollback()
        return False

    job.dispatch_attempts += 1
    job.dispatch_claimed_at = now
    # Persist the dispatch attempt before touching Redis. The queued job is the
    # durable outbox record and is therefore visible/recoverable first.
    db.commit()
    try:
        enqueue(job_id)
    except Exception:
        logger.exception("check-in dispatch failed", extra={"job_id": str(job_id)})
        job = db.get(BackgroundJob, job_id)
        if job is not None:
            job.dispatch_claimed_at = None
            db.commit()
        return False

    job = db.get(BackgroundJob, job_id)
    if job is None:
        return False
    job.dispatched_at = datetime.now(timezone.utc)
    job.dispatch_claimed_at = None
    db.commit()
    return True


def dispatch_pending_jobs(
    db: Session,
    enqueue: Callable[[uuid.UUID], None] = enqueue_check_in,
    *,
    limit: int = 100,
) -> int:
    claim_cutoff = datetime.now(timezone.utc) - _DISPATCH_LEASE
    job_ids = list(
        db.scalars(
            select(BackgroundJob.job_id)
            .where(
                BackgroundJob.status.in_([JobStatus.queued, JobStatus.processing]),
                BackgroundJob.dispatched_at.is_(None),
                or_(
                    BackgroundJob.dispatch_claimed_at.is_(None),
                    BackgroundJob.dispatch_claimed_at < claim_cutoff,
                ),
            )
            .order_by(BackgroundJob.created_at)
            .limit(limit)
        )
    )
    db.rollback()
    return sum(dispatch_background_job(db, job_id, enqueue) for job_id in job_ids)
