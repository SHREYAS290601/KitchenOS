import uuid

import pytest

from backend.app.models.background_job import BackgroundJob, JobStatus, initial_check_in_steps
from backend.app.models.consent import ConsentRecord, ConsentState, RetentionPolicy
from backend.app.models.image_evidence import ImageEvidenceRecord
from backend.app.workers.celery_app import celery, make_celery
from backend.app.workers.steps import (
    ConsentRevokedError,
    barcode_step,
    object_detection_step,
    ocr_step,
    product_enrichment_step,
    segmentation_step,
)


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


def add_job(db):
    user_id = uuid.uuid4()
    consent = ConsentRecord(
        user_id=user_id,
        state=ConsentState.granted_for_session,
        session_id="session-001",
        retention_policy=RetentionPolicy.delete_after_enrichment,
    )
    image = ImageEvidenceRecord(
        user_id=user_id,
        capture_context="post_shopping_check_in",
        processing_mode="silent_background_enrichment",
        linked_shopping_session_id="session-001",
        storage_uri=f"local://{uuid.uuid4()}.jpg",
        consent_status=ConsentState.granted_for_session,
        retention_policy=RetentionPolicy.delete_after_enrichment,
        stored_for_future_enrichment=True,
    )
    db.add_all([consent, image])
    db.flush()
    job = BackgroundJob(
        status=JobStatus.queued,
        user_id=user_id,
        image_ids=[str(image.image_id)],
        steps=initial_check_in_steps(),
    )
    db.add(job)
    db.commit()
    return job, consent


@pytest.mark.parametrize(
    "task,step_name",
    [
        (segmentation_step, "segmentation"),
        (object_detection_step, "object_detection"),
        (ocr_step, "ocr"),
        (barcode_step, "barcode"),
        (product_enrichment_step, "product_enrichment"),
    ],
)
def test_each_stub_completes_only_its_own_step(db, tables, task, step_name):
    job, _consent = add_job(db)
    before = [dict(step) for step in job.steps if step["step"] != step_name]

    result = task.delay(str(job.job_id)).get()
    db.expire_all()
    stored = db.get(BackgroundJob, job.job_id)

    assert result == {
        "job_id": str(job.job_id),
        "step": step_name,
        "candidates": [],
    }
    assert next(step for step in stored.steps if step["step"] == step_name)["status"] == "completed"
    assert [step for step in stored.steps if step["step"] != step_name] == before


def test_completed_step_retry_is_idempotent(db, tables):
    job, _consent = add_job(db)
    segmentation_step.delay(str(job.job_id)).get()

    second = segmentation_step.delay(str(job.job_id)).get()
    db.expire_all()
    stored = db.get(BackgroundJob, job.job_id)

    assert second["step"] == "segmentation"
    assert next(step for step in stored.steps if step["step"] == "segmentation")["status"] == "completed"


def test_step_failure_marks_step_and_job_failed(db, tables, monkeypatch):
    from backend.app.workers import steps

    job, _consent = add_job(db)

    def explode(_step_name, _job_id):
        raise RuntimeError("stub exploded")

    monkeypatch.setattr(steps, "run_stub", explode)
    with pytest.raises(RuntimeError, match="stub exploded"):
        ocr_step.delay(str(job.job_id)).get()

    db.expire_all()
    stored = db.get(BackgroundJob, job.job_id)
    assert stored.status == "failed"
    assert stored.error == "stub exploded"
    assert next(step for step in stored.steps if step["step"] == "ocr")["status"] == "failed"


def test_worker_rechecks_current_consent_before_processing(db, tables):
    job, consent = add_job(db)
    consent.state = ConsentState.revoked
    consent.session_id = None
    db.commit()

    with pytest.raises(ConsentRevokedError):
        segmentation_step.delay(str(job.job_id)).get()

    db.expire_all()
    stored = db.get(BackgroundJob, job.job_id)
    assert stored.status == "failed"
    assert "consent" in stored.error
    assert next(step for step in stored.steps if step["step"] == "segmentation")["status"] == "failed"
