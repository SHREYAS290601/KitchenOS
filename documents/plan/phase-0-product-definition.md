# PantryOps Edge Phase 0: Product Definition Implementation Plan

> **For agentic workers:** This is a documentation phase — no TDD loop, but every task still has a verification step. Steps use checkbox (`- [ ]`) syntax for tracking. REQUIRED ECC SKILLS: `/ecc:plan` (per-phase plan skeletons from the manifest), `/ecc:api-design` (lock the §19 contracts and SourcedField shape before any code).

**Goal:** Lock the product identity, data models, agent responsibilities, API contracts, and active/silent flows into versioned documents so every later phase has exactly one source of truth to cite.

**Architecture:** Per `documents/specs/architecture.md`. Phase 0 produces and validates the spec set; Phases 1–10 cite it. The SourcedField shape, evidence hierarchy, quantity scales, and the seven invariants are canonical after this phase — changing them later means changing the spec first, then the code.

**Out of scope for Phase 0:** Any executable code, database schemas, migrations, or scaffolding. If you are writing Python or TypeScript, you are in the wrong phase.

**Prerequisites:** `Manifest.md` at the repo root (exists, 29 sections).

---

## File structure (locked in by this plan)

```text
KitchenOS/
├── Manifest.md                    # exists — source of truth for product behavior
├── README.md                      # Task 2
├── CLAUDE.md                      # exists — agent working instructions
├── .env.example                   # Task 5
└── documents/
    ├── plan/
    │   ├── 00-overview.md         # exists
    │   └── phase-{0..10}-*.md     # this folder
    └── specs/
        ├── architecture.md        # exists — validate in Task 1
        ├── data-models.md         # exists — validate in Task 1
        ├── api-spec.md            # exists — validate in Task 1
        ├── agents.md              # exists — validate in Task 1
        └── adr/
            ├── 001-job-queue.md   # Task 4
            └── 002-sourced-field-storage.md
```

---

### Task 1: Validate the spec set against the manifest

**Files:**
- Review: `documents/specs/architecture.md`, `data-models.md`, `api-spec.md`, `agents.md`

- [ ] **Step 1: Cross-check data-models.md against Manifest §10–§14**

Every entity in §14 (PantryItem, ShoppingListItem, ShoppingConfirmationEvent, ImageEvidenceRecord, VisionDetection, SegmentationResult, OCRResult, ProductEnrichmentRecord, ConsumptionEvent, PreferenceRule, BackgroundJob) must appear in `data-models.md` with matching fields. The SourcedField shape must list `value, source, confidence, status, editable, last_updated` and the six status values.

- [ ] **Step 2: Cross-check agents.md against Manifest §15**

All 19 agents present, each with purpose, inputs, outputs, and forbidden actions. Every forbidden action from the manifest must survive verbatim in meaning — these become tests in later phases.

- [ ] **Step 3: Cross-check api-spec.md against Manifest §19**

All nine §19 endpoints present plus the support endpoints (`/images`, `/jobs/{id}`, pantry field actions, `/consumption/ad-hoc`, health). Every write endpoint's description must route through the ledger.

- [ ] **Step 4: Cross-check architecture.md invariants against Manifest §9, §24**

The seven invariants must cover: single write path, sourced writes, no estimate-over-confirmed, consent, LLM-never-writes, first-use review gate, no recipe auto-deduct. Guardrails 1–14 (§24) must each map to an invariant, an auditor check, or an agent forbidden action — list any orphans and fix the spec.

- [ ] **Step 5: Record discrepancies and fix the specs (not the manifest)**

---

### Task 2: Write README.md

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write the README** — one-line description, the seven product questions from Manifest §0, core identity quote, doc map table (Manifest / documents/plan / documents/specs / CLAUDE.md), MVP scope summary (§20), and a quickstart placeholder pointing at Phase 1.

- [ ] **Step 2: Verify** — every relative link resolves; a newcomer can find the right doc for "what is this," "how is it built," and "what do I build next" in one hop.

---

### Task 3: Verify flow coverage (active vs silent)

**Files:**
- Review: `documents/specs/architecture.md`, `documents/specs/data-models.md`

- [ ] **Step 1: Walk the nine demo steps (Manifest §27) against the specs** — pre-shopping planning, while-shopping question, cross-off, silent check-in, estimate review, recipe request, consumption update, first-use review, adapted next list. Each step must map to a named endpoint in `api-spec.md` and agents in `agents.md`.

- [ ] **Step 2: Verify the silent-mode rules are unambiguous** — silent processing runs only after an intentional post-shopping upload; consent states and retention policies enumerated; no image row without consent status.

---

### Task 4: Write the ADRs

**Files:**
- Create: `documents/specs/adr/001-job-queue.md`, `documents/specs/adr/002-sourced-field-storage.md`

- [ ] **Step 1: ADR 001 — Redis + Celery for background enrichment.** Context (multi-step DAG, survives restarts, per-step status), decision, alternatives rejected (BackgroundTasks, arq, RQ) with one line each, consequences (job row in same transaction; eager mode in tests).

- [ ] **Step 2: ADR 002 — SourcedField as JSONB columns + append-only change log.** Context (field-level provenance on every write), decision (JSONB on `pantry_item`, `ledger_change_log` for history), alternative rejected (normalized `field_provenance` table — join per field on every read), consequences (validators live in Pydantic, not the DB).

---

### Task 5: Write .env.example

**Files:**
- Create: `.env.example`

- [ ] **Step 1: Write the template** — `PANTRYOPS_DATABASE_URL`, `PANTRYOPS_REDIS_URL`, `PANTRYOPS_STORAGE_BACKEND` (local|minio|s3), `PANTRYOPS_S3_*`, `PANTRYOPS_LLM_API_KEY`, `PANTRYOPS_OFF_BASE_URL`, `PANTRYOPS_USDA_API_KEY` — placeholder values only, one comment per variable.

---

## Done criteria for Phase 0

- All four specs pass the cross-checks in Task 1 with zero unexplained divergence from the manifest.
- Every Manifest §24 guardrail maps to an invariant, auditor check, or agent forbidden action.
- README, two ADRs, and `.env.example` exist.
- A reviewer can start Phase 1 citing only `documents/specs/` — without reopening the manifest.

## Next phase

[Phase 1 — Mobile Shell and Backend](phase-1-mobile-shell-and-backend.md): the FastAPI chassis, Expo shell, Postgres/Redis/MinIO compose, Alembic, and the offline checklist cache.
