# ADR 001: Redis + Celery for background enrichment

**Status:** Accepted (2026-07-12)

## Context

Silent check-in processing is a multi-step DAG: image intake → detection → segmentation → OCR/barcode → product enrichment → ledger proposal. It must survive backend restarts, retry individual steps without redoing the whole chain, and expose per-step status so the mobile app can show "3 of 5 steps done" for a background job. FastAPI's request lifecycle cannot hold work this long, and losing a half-finished enrichment on deploy is unacceptable.

## Decision

Use **Celery with Redis** as broker and result backend. Each enrichment step is a Celery task; the check-in pipeline is a Celery chain/chord. Job state lives in the `background_job` table (not only in Redis), written by the tasks themselves.

## Alternatives rejected

- **FastAPI `BackgroundTasks`** — dies with the worker process; no retries, no persistence, no per-step status.
- **arq** — asyncio-native and lightweight, but no first-class task chaining/DAG primitives; we would rebuild Celery's canvas by hand.
- **RQ** — simple, but retries and chaining are bolt-ons, and there is no eager mode as clean as Celery's for tests.

## Consequences

- Every job enqueue writes the `background_job` row **in the same database transaction** as the triggering change, so a job row never references state that was rolled back.
- Tests run with `task_always_eager = True` — the whole pipeline executes synchronously in-process, no Redis needed for unit tests.
- Redis becomes a runtime dependency (`docker compose` service alongside Postgres and MinIO).
