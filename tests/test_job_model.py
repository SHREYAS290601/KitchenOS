import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from backend.app.models.background_job import (
    CHECK_IN_STEPS,
    BackgroundJob,
    JobStatus,
    StepStatus,
    initial_check_in_steps,
)


def test_background_job_round_trips_steps_and_nullable_completion_fields(db, tables):
    job = BackgroundJob(
        job_type="grocery_image_check_in",
        status=JobStatus.queued,
        user_id=uuid.uuid4(),
        image_ids=[str(uuid.uuid4()), str(uuid.uuid4())],
        steps=initial_check_in_steps(),
    )
    db.add(job)
    db.commit()
    db.expire_all()

    stored = db.get(BackgroundJob, job.job_id)

    assert stored is not None
    assert stored.image_ids == job.image_ids
    assert [step["step"] for step in stored.steps] == list(CHECK_IN_STEPS)
    assert stored.completed_at is None
    assert stored.error is None


def test_invalid_job_status_is_rejected_by_database(db, tables):
    db.add(
        BackgroundJob(
            job_type="grocery_image_check_in",
            status="not-a-real-status",
            user_id=uuid.uuid4(),
            image_ids=[str(uuid.uuid4())],
            steps=initial_check_in_steps(),
        )
    )

    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_set_step_status_replaces_json_and_persists_after_reload(db, tables):
    job = BackgroundJob(
        job_type="grocery_image_check_in",
        user_id=uuid.uuid4(),
        image_ids=[str(uuid.uuid4())],
        steps=initial_check_in_steps(),
    )
    db.add(job)
    db.commit()
    original_steps = job.steps

    job.set_step_status("segmentation", StepStatus.processing)
    db.commit()
    db.expire_all()

    stored = db.get(BackgroundJob, job.job_id)
    assert stored is not None
    assert stored.steps is not original_steps
    assert next(step for step in stored.steps if step["step"] == "segmentation")["status"] == "processing"
    assert next(step for step in stored.steps if step["step"] == "ocr")["status"] == "queued"


@pytest.mark.parametrize("step,status", [("unknown", "completed"), ("ocr", "unknown")])
def test_set_step_status_rejects_unknown_values(step, status):
    job = BackgroundJob(
        user_id=uuid.uuid4(),
        image_ids=[str(uuid.uuid4())],
        steps=initial_check_in_steps(),
    )

    with pytest.raises(ValueError):
        job.set_step_status(step, status)


def test_all_steps_completed_only_when_every_step_is_completed():
    job = BackgroundJob(
        user_id=uuid.uuid4(),
        image_ids=[str(uuid.uuid4())],
        steps=initial_check_in_steps(),
    )
    assert job.all_steps_completed() is False

    for step in CHECK_IN_STEPS:
        job.set_step_status(step, StepStatus.completed)

    assert job.all_steps_completed() is True
