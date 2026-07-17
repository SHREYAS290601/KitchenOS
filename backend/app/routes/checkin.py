import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.deps import (
    DevUser,
    enforce_checkin_rate_limit,
    get_current_user,
    get_db,
)
from backend.app.models.background_job import BackgroundJob
from backend.app.schemas.checkin import CheckInRequest, CheckInResponse, JobStatusOut
from backend.app.services.checkin import (
    CheckInImagesNotFound,
    CheckInConsentRequired,
    InvalidCheckInImages,
    create_check_in,
    dispatch_background_job,
    enqueue_check_in,
)

router = APIRouter(tags=["check-in"])


@router.post("/check-in/groceries", response_model=CheckInResponse, status_code=202)
def post_grocery_check_in(
    payload: CheckInRequest,
    db: Session = Depends(get_db),
    user: DevUser = Depends(get_current_user),
    _rate_limit: None = Depends(enforce_checkin_rate_limit),
) -> CheckInResponse:
    try:
        job = create_check_in(db, user_id=user.user_id, request=payload)
        db.commit()
    except CheckInImagesNotFound as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail="one or more images were not found") from exc
    except InvalidCheckInImages as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except CheckInConsentRequired as exc:
        db.rollback()
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception:
        db.rollback()
        raise

    dispatch_background_job(db, job.job_id, enqueue_check_in)
    return CheckInResponse(job_id=job.job_id, status=job.status, steps=job.steps)


@router.get("/jobs/{job_id}", response_model=JobStatusOut)
def get_job_status(
    job_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: DevUser = Depends(get_current_user),
) -> JobStatusOut:
    job = db.scalar(
        select(BackgroundJob).where(
            BackgroundJob.job_id == job_id,
            BackgroundJob.user_id == user.user_id,
        )
    )
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return JobStatusOut(
        job_id=job.job_id,
        job_type=job.job_type,
        status=job.status,
        image_ids=job.image_ids,
        steps=job.steps,
        created_at=job.created_at.isoformat(),
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
        error=job.error,
    )
