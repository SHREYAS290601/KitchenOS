import uuid

import pytest

from backend.app.models.background_job import BackgroundJob, JobStatus, initial_check_in_steps
from backend.app.models.consent import ConsentRecord, ConsentState, RetentionPolicy
from backend.app.models.image_evidence import ImageEvidenceRecord
from backend.app.models.pantry_item import PantryItem
from backend.app.schemas.sourced_field import EvidenceSource, FieldStatus, SourcedField
from backend.app.services.background_enrichment import apply_enrichment_proposal
from backend.app.workers.pipeline import run_check_in_pipeline
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


def test_pipeline_runs_in_manifest_order_and_completes_job(db, tables, monkeypatch):
    from backend.app.workers import steps

    job, _consent = add_job(db)
    observed = []

    def observe(step_name, job_id):
        observed.append(step_name)
        return {"job_id": str(job_id), "step": step_name, "candidates": []}

    monkeypatch.setattr(steps, "run_stub", observe)

    run_check_in_pipeline.delay(str(job.job_id)).get()
    db.expire_all()
    stored = db.get(BackgroundJob, job.job_id)

    assert observed == [
        "segmentation",
        "object_detection",
        "ocr",
        "barcode",
        "product_enrichment",
    ]
    assert stored.status == "completed"
    assert stored.completed_at is not None
    assert stored.all_steps_completed() is True


def test_pipeline_failure_stops_later_steps(db, tables, monkeypatch):
    from backend.app.workers import steps

    job, _consent = add_job(db)
    observed = []

    def fail_at_ocr(step_name, job_id):
        observed.append(step_name)
        if step_name == "ocr":
            raise RuntimeError("ocr failed")
        return {"job_id": str(job_id), "step": step_name, "candidates": []}

    monkeypatch.setattr(steps, "run_stub", fail_at_ocr)

    with pytest.raises(RuntimeError, match="ocr failed"):
        run_check_in_pipeline.delay(str(job.job_id)).get()

    db.expire_all()
    stored = db.get(BackgroundJob, job.job_id)
    assert observed == ["segmentation", "object_detection", "ocr"]
    assert stored.status == "failed"
    assert next(step for step in stored.steps if step["step"] == "barcode")["status"] == "queued"


def test_background_agent_emits_estimates_and_flags_low_confidence():
    from backend.app.agents.background_enrichment import (
        BackgroundEnrichmentAgent,
        EnrichmentCandidate,
        EnrichmentContext,
    )

    result = BackgroundEnrichmentAgent().run(
        EnrichmentContext(
            candidates=[
                EnrichmentCandidate(field_name="brand", value="Acme", confidence=0.9),
                EnrichmentCandidate(field_name="product_name", value="Soup", confidence=0.4),
            ]
        )
    )

    assert all(candidate.field.status == FieldStatus.estimated for candidate in result.candidates)
    assert all(candidate.field.source == EvidenceSource.silent_check_in for candidate in result.candidates)
    assert result.needs_user_review is True


def test_enrichment_service_preserves_user_confirmed_field_as_conflict(db, tables):
    from backend.app.agents.background_enrichment import (
        BackgroundEnrichmentAgent,
        EnrichmentCandidate,
        EnrichmentContext,
    )

    item = PantryItem(
        user_id=uuid.uuid4(),
        brand=SourcedField(
            value="Trusted Brand",
            source=EvidenceSource.user_confirmed,
            confidence=1,
            status=FieldStatus.user_confirmed,
        ).model_dump(mode="json"),
        quantity_type="unknown",
        status="stored",
    )
    db.add(item)
    db.commit()
    proposal = BackgroundEnrichmentAgent().run(
        EnrichmentContext(
            candidates=[
                EnrichmentCandidate(
                    field_name="brand",
                    value="Estimated Brand",
                    confidence=0.88,
                )
            ]
        )
    )

    results = apply_enrichment_proposal(db, item, proposal)
    db.commit()

    assert results[0].outcome == "conflict"
    assert item.brand["value"] == "Trusted Brand"
    assert item.brand["conflict_candidates"][0]["status"] == "conflicting"
