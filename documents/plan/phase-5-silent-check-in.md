# PantryOps Edge Phase 5: Silent Grocery Check-In Implementation Plan

> **For agentic workers:** Implement task-by-task with strict TDD: write the failing test, watch it fail, implement, watch it pass, commit. Steps use checkbox (`- [ ]`) syntax. REQUIRED ECC SKILLS before starting: `/ecc:redis-patterns` (broker/result-backend config), `/ecc:python-patterns` (Celery chain + durable job model), `/ecc:backend-patterns` (job-row-in-same-transaction durability), `/ecc:python-testing` (eager-mode pipeline tests).

**Goal:** Post-shopping multi-image upload, a durable background-job model, a Celery pipeline skeleton with per-step status, and image-evidence wiring — the full silent check-in shape running end to end with **stub** vision tasks, so Phase 6 only swaps stubs for real models.

**Architecture:** Per `documents/specs/architecture.md` §5 (Redis + Celery decision, durability rule) and `documents/specs/data-models.md` §4.12 (BackgroundJob). The `BackgroundJob` row is written **in the same DB transaction** as the check-in request — a queue failure can delay processing but never lose the intent. The job row, not Celery, is the durable source of truth for step status. Consent is enforced at the endpoint AND in the worker (invariant 4). The Mobile Check-In Agent never claims final identity; the Background Enrichment Agent creates estimates only and never touches user-confirmed fields (invariant 3).

**Tech Stack:** Celery 5 (Redis broker + result backend, eager mode in tests), Redis 7 (already in compose from Phase 1), SQLAlchemy 2.0, FastAPI, pytest. Mobile: Expo image picker, Jest + @testing-library/react-native.

**Out of scope for Phase 5** (later plans): real segmentation/detection/OCR/barcode models (Phase 6 — stubs here), product API enrichment (Phase 7), recipe/consumption logic (Phase 8).

**Prerequisites:** Phases 1–4 complete: compose stack (postgres/redis/minio) healthy, ledger write path (`services/ledger.py::apply_update`) green, consent service + image storage (`services/consent.py`, `services/image_storage.py`, `storage/`) from Phase 4 working.

---

## File structure (locked in by this plan)

```text
backend/app/
├── models/background_job.py        # §14.11 job row: status, image_ids, steps
├── schemas/checkin.py              # CheckInRequest / CheckInResponse / JobStatusOut
├── services/checkin.py             # create job + enqueue in ONE transaction
├── routes/checkin.py               # POST /check-in/groceries, GET /jobs/{job_id}
├── workers/
│   ├── celery_app.py               # Celery config (broker/backend from Settings)
│   ├── steps.py                    # stub tasks: segmentation…enrichment, each updates step status
│   └── pipeline.py                 # chain() ordering the steps + retention beat task
└── agents/
    ├── mobile_check_in.py          # §15.5 — starts silent enrichment, never claims identity
    └── background_enrichment.py    # §15.6 — orchestrates steps, estimates only

backend/alembic/versions/<job_model>.py
tests/
├── test_job_model.py
├── test_checkin_api.py
├── test_checkin_consent.py
└── test_pipeline_stubs.py
mobile/screens/CheckInScreen.tsx
mobile/__tests__/CheckInScreen.test.tsx
```

Workers stay thin: they load context, call `services/` functions, persist, update job state. No worker imports ORM write helpers for pantry fields — everything goes through `apply_update()`.

---

### Task 1: Celery app wired to Settings

**Files:**
- Create: `backend/app/workers/__init__.py`, `backend/app/workers/celery_app.py`
- Test: `tests/test_pipeline_stubs.py` (start)

- [ ] **Step 1: Write the failing test** — `tests/test_pipeline_stubs.py`:

```python
from backend.app.workers.celery_app import celery, make_celery


def test_celery_configured_from_settings(monkeypatch):
    monkeypatch.setenv("PANTRYOPS_REDIS_URL", "redis://localhost:6379/0")
    app = make_celery()
    assert app.conf.broker_url.startswith("redis://")
    assert app.conf.result_backend.startswith("redis://")


def test_eager_mode_runs_inline():
    celery.conf.task_always_eager = True

    @celery.task
    def add(a, b):
        return a + b

    assert add.delay(2, 3).get() == 5
```

- [ ] **Step 2: Run to verify it fails** — `uv run pytest tests/test_pipeline_stubs.py -v` → FAIL (ImportError).

- [ ] **Step 3: Implement `celery_app.py`** — `make_celery()` reads `Settings`, sets broker + result backend to `redis_url`, `task_serializer="json"`, and exposes a module-level `celery` instance. Test fixture in `conftest.py` sets `task_always_eager = True` and `task_eager_propagates = True` for the whole suite.

- [ ] **Step 4: Run to verify it passes.**

- [ ] **Step 5: Commit** — `feat(workers): celery app configured from settings with eager test mode`

---

### Task 2: BackgroundJob model

**Files:**
- Create: `backend/app/models/background_job.py`, migration
- Test: `tests/test_job_model.py`

- [ ] **Step 1: Write the failing test** — round-trip a job with `job_type="grocery_image_check_in"`, `status="queued"`, `image_ids=["img_001","img_002"]` (JSONB), and the five-step `steps` array from `data-models.md` §4.12; assert `completed_at is None` and `error is None`; assert an invalid `status` value is rejected by the model's enum/check constraint.

- [ ] **Step 2: Run to verify it fails** — FAIL (ImportError).

- [ ] **Step 3: Implement the model** — columns per `data-models.md` §4.12: UUID PK, `job_type`, `status` (enum: `queued | processing | completed | failed | needs_review`), `user_id`, `image_ids` JSONB, `steps` JSONB (list of `{step, status}`), timestamps, `error`. Helper methods `set_step_status(step, status)` and `all_steps_completed()`. Generate + hand-review the Alembic migration.

- [ ] **Step 4: Run to verify it passes** — includes `uv run pytest tests/test_migrations.py -v` (parity test from Phase 1 still green).

- [ ] **Step 5: Commit** — `feat(checkin): durable background job model with per-step status`

---

### Task 3: Check-in service + route — job row in ONE transaction

This is the durability core of the phase: the job row and the enqueue intent commit atomically with the request.

**Files:**
- Create: `backend/app/schemas/checkin.py`, `backend/app/services/checkin.py`, `backend/app/routes/checkin.py`
- Modify: `backend/app/main.py` (mount router)
- Test: `tests/test_checkin_api.py`

- [ ] **Step 1: Write the failing tests** — `tests/test_checkin_api.py`:

```python
def test_checkin_creates_job_and_links_images(client, db, consented_images):
    r = client.post("/check-in/groceries", json={
        "shopping_session_id": "session_001",
        "image_ids": consented_images,
        "processing_mode": "silent_background_enrichment",
    })
    assert r.status_code == 202
    body = r.json()
    job = db.get(BackgroundJob, body["job_id"])
    assert job.status in ("queued", "processing", "completed")  # eager mode may complete
    assert job.image_ids == consented_images


def test_checkin_with_zero_images_422(client):
    r = client.post("/check-in/groceries", json={
        "shopping_session_id": "session_001", "image_ids": [],
        "processing_mode": "silent_background_enrichment",
    })
    assert r.status_code == 422  # silent mode never runs without user photos


def test_job_status_endpoint_returns_steps(client, db, queued_job):
    r = client.get(f"/jobs/{queued_job.job_id}")
    assert r.status_code == 200
    assert [s["step"] for s in r.json()["steps"]][0] == "image_storage"
```

- [ ] **Step 2: Run to verify they fail** — FAIL (404, routes don't exist).

- [ ] **Step 3: Implement** — `services/checkin.py::create_check_in(db, user, request)`: validates images exist and belong to the user, writes the `BackgroundJob` row, flushes, and registers the Celery enqueue as an after-commit hook (SQLAlchemy `event.listens_for(session, "after_commit")` or equivalent) so **the row commits with the request and the enqueue only fires on successful commit**. Route returns 202 with `job_id` + initial steps. `GET /jobs/{job_id}` serializes the job row (the durable truth — never Celery state).

- [ ] **Step 4: Run to verify they pass.**

- [ ] **Step 5: Commit** — `feat(checkin): check-in endpoint with transactional job creation and status route`

---

### Task 4: Consent enforcement on the silent path

**Files:**
- Modify: `backend/app/services/checkin.py`
- Test: `tests/test_checkin_consent.py`

- [ ] **Step 1: Write the failing tests** — check-in with images whose `consent_status` is `denied` or `not_requested` → 403 with a detail naming the offending image; check-in with `granted_for_session` and `always_granted` → 202; the worker-side guard (Task 6) re-asserts consent before processing and marks the job `failed` with a consent error if it changed to `revoked` between request and execution.

- [ ] **Step 2: Run to verify they fail.**

- [ ] **Step 3: Implement** — `services/checkin.py` asserts `consent_status ∈ {granted_for_single_image, granted_for_session, always_granted}` per image (invariant 4); the same predicate is exported as `consent_allows_processing(image)` for the worker.

- [ ] **Step 4: Run to verify they pass.**

- [ ] **Step 5: Commit** — `feat(checkin): consent enforced at endpoint and exported for worker re-check`

---

### Task 5: Mobile Check-In Agent

**Files:**
- Create: `backend/app/agents/mobile_check_in.py`
- Test: append to `tests/test_checkin_api.py`

- [ ] **Step 1: Write the failing tests** — the agent's `run(context)` with zero images raises/refuses (`must not run without user-provided images`); with valid images returns `{job_id, status: "processing_in_background"}` and its output text never contains a product identity claim (assert response schema has no `brand`/`product_name` fields — §15.5 "must not claim final identity immediately").

- [ ] **Step 2: Run to verify they fail.**

- [ ] **Step 3: Implement** — thin agent class delegating to `services/checkin.py`; returns typed proposal only.

- [ ] **Step 4: Verify pass. Commit** — `feat(agents): mobile check-in agent with no-identity-claim output`

---

### Task 6: Stub pipeline steps with per-step status

**Files:**
- Create: `backend/app/workers/steps.py`
- Test: append to `tests/test_pipeline_stubs.py`

- [ ] **Step 1: Write the failing tests** — for each of `segmentation_step`, `object_detection_step`, `ocr_step`, `barcode_step`, `product_enrichment_step`: running the task (eager) transitions that step's status `queued → completed` on the job row and leaves the others untouched; a step that raises marks its step `failed` and the job `failed` with the error recorded; every step calls `consent_allows_processing` first and aborts the job cleanly on revoked consent.

- [ ] **Step 2: Run to verify they fail.**

- [ ] **Step 3: Implement** — five Celery tasks, each: load job, re-check consent, set step `processing`, do stub work (return an empty typed result), set step `completed`. Shared `@job_step("ocr")` decorator handles load/status/error bookkeeping so the stubs are one line of body each — Phase 6 replaces only the body.

- [ ] **Step 4: Verify pass. Commit** — `feat(workers): stub pipeline steps with per-step status bookkeeping`

---

### Task 7: Pipeline chain + Background Enrichment Agent

**Files:**
- Create: `backend/app/workers/pipeline.py`, `backend/app/agents/background_enrichment.py`
- Test: append to `tests/test_pipeline_stubs.py`

- [ ] **Step 1: Write the failing tests** — `run_check_in_pipeline(job_id)` (eager) moves the job `queued → processing → completed` with steps completing **in manifest §7 order** (segmentation → detection → OCR → barcode → enrichment); the Background Enrichment Agent, given a stub candidate for a field whose stored status is `user_confirmed`, files it as `conflicting` via `apply_update()` and never applies it (invariant 3); nothing in the run marks any estimated field as confirmed.

- [ ] **Step 2: Run to verify they fail.**

- [ ] **Step 3: Implement** — `pipeline.py::run_check_in_pipeline` builds `chain(segmentation_step.si(job_id), …, product_enrichment_step.si(job_id))`; final link flips job status. `background_enrichment.py` consumes step outputs and routes every candidate through `apply_update()` with `source="silent_check_in"`, flagging low-confidence fields `needs_user_review` (§15.6).

- [ ] **Step 4: Verify pass. Commit** — `feat(workers): ordered check-in chain with estimates-only enrichment agent`

---

### Task 8: Retention beat task

**Files:**
- Modify: `backend/app/workers/pipeline.py`
- Test: append to `tests/test_checkin_consent.py`

- [ ] **Step 1: Write the failing tests** — after a completed job, an image with `retention_policy="delete_after_enrichment"` is deleted from storage and its row marked deleted; `keep_for_pantry_memory` images survive; `delete_after_answer` images from Phase 4 active queries are swept too.

- [ ] **Step 2: Run to verify they fail.**

- [ ] **Step 3: Implement** — `enforce_retention` Celery task registered on beat (hourly) and also invoked as the pipeline's final link; deletes via the `storage/` abstraction only.

- [ ] **Step 4: Verify pass. Commit** — `feat(workers): retention enforcement task honoring per-image policy`

---

### Task 9: Check-in screen (mobile)

**Files:**
- Create: `mobile/screens/CheckInScreen.tsx`
- Test: `mobile/__tests__/CheckInScreen.test.tsx`

- [ ] **Step 1: Write the failing tests** — multi-photo picker renders with an accessible label ("Add grocery photos"); submitting with photos calls the client's `postCheckIn` and shows "Processing in background — you can keep using the app" in a live region (`accessibilityLiveRegion="polite"`); job status polling renders each step's name + status as text (never color alone); zero-photo submit is blocked with an error message naming the field.

- [ ] **Step 2: Run to verify they fail** — `npx jest mobile/__tests__/CheckInScreen.test.tsx` → FAIL.

- [ ] **Step 3: Implement** — Expo image picker (multi-select), typed client calls, polled `GET /jobs/{id}` with backoff, all controls keyboard-reachable with visible focus.

- [ ] **Step 4: Verify pass. Commit** — `feat(mobile): accessible check-in screen with background status polling`

---

## Done criteria for Phase 5

- Check-in creates the job row and image links in one transaction; enqueue fires only after commit (verified by test).
- Celery chain runs all five stub steps end to end in eager mode with correct per-step status and §7 ordering.
- Consent enforced at the endpoint and re-checked in every worker step; zero-image check-in is impossible.
- Background Enrichment Agent provably never touches user-confirmed fields and never confirms an estimate.
- Retention policies enforced by the beat task; mobile check-in screen accessible and green.

## Next phase

[Phase 6 — Vision/OCR Enrichment](phase-6-vision-ocr-enrichment.md): the stub step bodies become real detection, segmentation, OCR, and barcode reading — the pipeline shape does not change.
