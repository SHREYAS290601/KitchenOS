# PantryOps Edge — Architecture Specification

Source of truth for product behavior: `Manifest.md` (repo root). This spec locks the technical architecture the build phases implement. Plan documents in `documents/plan/` cite this file — do not restate architecture there; change it here.

---

## 1. Shape of the system

One mobile app, one hosted backend, one database. PantryOps Edge is **not** microservices — the manifest (§17) describes a single hosted backend, so we build a single-package Python backend and keep the LLM/agent/vision code in one import graph. No premature service boundaries.

```text
React Native App (Expo)
  ├── camera capture + barcode scanning
  ├── local shopping checklist cache (offline-capable)
  ├── pantry snapshot cache
  ├── user edits (confirm / edit / reject / leave-as-estimate)
  └── active chat/query interface

Hosted Backend (FastAPI, single package)
  ├── API layer               (routes/)
  ├── pantry ledger           (services/ledger.py — the ONLY write path)
  ├── image storage           (storage/ abstraction: local | MinIO | S3)
  ├── background jobs         (Celery + Redis)
  ├── vision services         (vision/: detect, segment, OCR, barcode)
  ├── product enrichment      (products/: Open Food Facts, USDA)
  ├── LLM agent orchestration (agents/: 19 agents, LangGraph + LangSmith)
  └── audit layer             (agents/auditor.py — last gate on every output)
```

## 2. Monorepo layout (locked)

```text
pantryops-edge/
├── README.md
├── MANIFEST.md
├── pyproject.toml                 # single backend package + dev deps (uv)
├── uv.lock
├── docker-compose.yml             # postgres:16 + redis:7 + minio (local S3)
├── .env.example
├── .gitignore
├── alembic.ini
├── mobile/                        # Expo React Native app (own package.json)
│   ├── app/                       # expo-router routes
│   ├── screens/
│   ├── components/
│   ├── camera/
│   ├── storage/                   # local checklist + pantry snapshot cache
│   └── api/                       # typed backend client
├── backend/
│   ├── alembic/                   # env.py + versions/
│   └── app/
│       ├── main.py                # create_app() factory
│       ├── config.py              # Settings (pydantic-settings, PANTRYOPS_ prefix)
│       ├── db.py                  # engine, Base, session factory
│       ├── deps.py                # get_db, get_settings, get_current_user
│       ├── models/                # SQLAlchemy ORM, one file per aggregate
│       ├── schemas/               # Pydantic request/response, one file per domain
│       ├── routes/                # FastAPI routers, one file per API group
│       ├── services/              # business logic (ledger, consent, checkin, …)
│       ├── workers/               # Celery app + tasks (enrichment pipeline)
│       ├── agents/                # 19 agents from Manifest §15
│       ├── pantry/                # quantity.py, lifecycle.py, preferences.py
│       ├── vision/                # detector, segmenter, ocr, barcode, preprocessing
│       ├── products/              # open_food_facts, usda, normalization
│       ├── recipes/               # recommender, matcher, deduction
│       ├── evaluation/            # metric suites (Manifest §22)
│       └── storage/               # object-store abstraction (local/minio/S3)
├── tests/                         # pytest; mirrors backend/app tree
├── documents/                     # this folder: plan/ + specs/
└── data/                          # samples, public datasets, user_uploads, exports
```

## 3. Backend layering (strictly one direction)

```text
routes/  →  schemas/  →  services/  →  models/
```

- `routes/` — HTTP contract only: parse, authorize, delegate, serialize. One router per API group in `api-spec.md`. Routes never touch the engine directly; they depend on `get_db`.
- `schemas/` — Pydantic v2 models. The recurring **SourcedField** shape (`value, source, confidence, status, editable, last_updated`) lives here as a reusable generic (see `data-models.md`).
- `services/` — domain logic with a dependency-injected `Session`. The ledger rules (Manifest §15.12) are enforced here and nowhere else.
- `workers/` — Celery tasks. Thin: load context, call the same `services/` functions, persist, update job state.
- `agents/` — sit **above** `services/`, never beside the ORM. Agents produce proposals; tools commit them (see §7 below).

App factory pattern: `backend/app/main.py::create_app()` builds Settings, engine, session factory (stored on `app.state`), mounts routers and exception handlers. No module-level engine — tests override `get_db`.

## 4. Database

- **PostgreSQL 16** (docker compose locally; hosted in production). SQLite is rejected: JSONB source-metadata columns and the preference queries want Postgres.
- **SQLAlchemy 2.0 sync + psycopg 3.** Sync is simpler for Celery workers and TestClient; async is not needed at MVP scale.
- **Single schema** `pantryops`.
- **Sourced fields as JSONB**: pantry-item fields that carry provenance (`canonical_name`, `display_name`, `category`, `brand`, `product_name`, `quantity_value`) are JSONB columns matching the SourcedField shape, plus an append-only `ledger_change_log` table for audit history. Fast reads, atomic item updates, no join per field.
- **Alembic from Phase 1.** `env.py` targets `Base.metadata`; URL from `PANTRYOPS_DATABASE_URL`. Tests build via `create_all`; environments use migrations; a standing test proves they agree. Never edit a shipped migration.

## 5. Background jobs: Redis + Celery

The silent check-in pipeline (Manifest §7) is a real multi-step DAG — segmentation → detection → OCR → barcode → enrichment → audit — long-running, must survive API restarts, and needs per-step status for the `BackgroundJob` model.

**Decision: Celery with Redis broker/result backend.**

Rejected alternatives: FastAPI `BackgroundTasks` (dies with the process, no retries), `arq` (weaker chaining/observability), `RQ` (no workflow primitives). Celery gives `chain`/`chord`, per-task retry, and result backends for step status.

Durability rule: **the `BackgroundJob` row is written in the same DB transaction as the check-in request**, so a queue failure can delay processing but never lose the intent. The job row is the durable source of truth for step status; Celery is only the executor. Tests run Celery in eager mode.

## 6. Object storage for images

- `backend/app/storage/` exposes `put_image`, `get_uri`, `delete`, `open` behind an interface. Implementations selected by config: local filesystem for quick dev, **MinIO** in docker compose (same S3 API as production, so code paths never fork), S3-compatible in production.
- `storage_uri` / `mask_uri` / `crop_uri` on the evidence records are opaque URIs the abstraction resolves.
- **Retention is data, not code**: every image row carries `consent_status` and `retention_policy`. A Celery beat task enforces `delete_after_answer` / `delete_after_enrichment` / `keep_until_manually_deleted`.

## 7. LLM agent layer

- Agents produce **proposals, never writes**. Any ledger change is a structured tool call routed into `services/ledger.py::apply_update()` — the single write path. The LLM emits JSON matching a Pydantic tool schema; the tool validates and commits. This is the manifest's Evidence Rule (§9) and §15.12 "LLM cannot directly mutate inventory," made structural.
- **Orchestration:** LangGraph (stateful agent graphs) with LangSmith tracing — decided 2026-07-13, superseding the earlier custom-state-machine choice (ADR 003). `agents/input_router.py` is the entry node that normalizes intent and routes to downstream agent nodes; each agent remains a typed unit `run(context) -> proposal`. The invariant is unchanged: LLM/agent nodes only produce proposals — every ledger write still goes through `services/ledger.py::apply_update()` as a structured tool call.
- **LLM:** `deepseek/deepseek-v4-flash` served through OpenRouter (fast, low-latency planning/explanation). Model id and key come from env (`PANTRYOPS_LLM_MODEL`, `PANTRYOPS_LLM_API_KEY`); no model name is hardcoded in agent code.
- **Auditor last:** `agents/auditor.py` runs on every final user-facing output and every batch of ledger proposals before commit. It checks dietary-restriction violations, recipes using unavailable items, unsourced updates, low-confidence-shown-as-fact, preference overgeneralization, and silent-mode-without-consent. The auditor can block or downgrade a proposal to "needs review."
- **Structured output everywhere:** agents return Pydantic models, so `source`, `confidence`, `status` are never optional free-text.

## 8. The seven invariants (test-enforced, not conventions)

1. **Single ledger write path.** All pantry mutations go through `services/ledger.py::apply_update()`. Routes, workers, and agents never mutate `PantryItem` fields directly. Enforced by an import/AST guard test.
2. **Field-level source metadata on every write.** `apply_update()` refuses any field change lacking `source`, `confidence`, `status`. The SourcedField model makes them required.
3. **User-confirmed/edited fields are never overwritten by estimates.** If the stored `status ∈ {user_confirmed, user_edited}`, an incoming estimate is stored as `conflicting` and surfaced to the Estimate Review Agent — never applied.
4. **No silent enrichment without consent.** The check-in endpoint and the enrichment worker both assert `consent_status ∈ {granted_for_session, always_granted}` before storing or processing images. The auditor re-checks.
5. **The LLM never mutates the ledger directly.** Agents return proposals; only tools call `apply_update()`. Enforced by module boundaries plus a test that the agents package does not import ORM write helpers.
6. **Reviews are not strong preferences before first use.** `services/preferences.py` downgrades pre-first-use input to `preference_hint`.
7. **Recipes never auto-deduct.** Deduction only occurs on the `confirm-cooked` path.

## 9. Evidence-hierarchy enforcement pattern

The Manifest §15.12 rules become code in one module: `services/ledger.py`.

`apply_update(item, field, incoming: SourcedField)` implements a precedence function over `source`:

```text
user_edited / user_confirmed   (highest)
> checklist_cross_off
> barcode
> receipt_ocr
> label_ocr
> product_detection
> segmentation
> silent_check_in
> api_enrichment
> web_enrichment
> llm_inference                (never a truth source)
```

An incoming field is applied only if its precedence ≥ the stored field's precedence **and** it does not downgrade a user-confirmed/edited value; otherwise it is recorded as `conflicting`. Every applied change writes a `ledger_change_log` row in the same transaction — "no unsourced write" and "full audit trail" are structural, not reviewer-dependent.

## 10. Testing strategy

- **Backend:** pytest + FastAPI TestClient against real local Postgres (session-scoped engine, function-scoped `db` fixture that truncates tables). `get_db` overridden in tests. Celery in eager mode. Vision and product-API tests use recorded fixtures — never live model downloads or network calls in unit tests; a separate `-m integration` suite exercises real models/APIs. Every feature ships test-first (red → green → commit).
- **Mobile:** Jest + `@testing-library/react-native` for components/screens; Maestro (or Detox) for a small E2E smoke. Accessibility assertions are part of component tests: accessible names on all controls, visible focus, live regions for async status, information never conveyed by color alone (WCAG 2.1 AA).
- **Invariants:** each of the seven invariants has at least one dedicated test.

## 11. Commit conventions

Conventional Commits with a scope per area: `feat(ledger):`, `feat(vision):`, `feat(checkin):`, `feat(mobile):`, `chore:`, `test:`, `fix:`. One logical change per commit; tests land with the code they cover; migrations land with their model change. Commit after each green task step.
