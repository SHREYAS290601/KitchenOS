# PantryOps Edge Phase 10: Evaluation and Demo Implementation Plan

> **For agentic workers:** Implement task-by-task with strict TDD where a test applies; harness tasks still end with a verify step. Steps use checkbox (`- [ ]`) syntax. REQUIRED ECC SKILLS before starting: `/ecc:eval-harness` (§22 metric suites with thresholds), `/ecc:e2e-testing` (the nine-step demo flow), `/ecc:verification-loop` (assert the seven invariants hold across the full run).

**Goal:** Prove the MVP end to end: a seeded demo user, curated sample data, metric suites covering Manifest §22, and one E2E test that walks all nine demo-script steps (§27) while asserting the seven architecture invariants hold throughout.

**Architecture:** Per `documents/specs/architecture.md` §10. No new product surface — this phase builds the evaluation harness in `backend/app/evaluation/` and demo assets in `data/samples/` + `scripts/`. Runs are deterministic: recorded sample images, seeded user, Celery in eager mode, LLM calls stubbed with recorded responses in the E2E test (a separate `-m integration` marker exercises the live model).

**Tech Stack:** Python 3.12, pytest (markers: default unit/E2E-deterministic, `integration` for live models/APIs), FastAPI TestClient, Celery eager mode.

**Out of scope for Phase 10** (post-MVP): production deployment / CI-CD to cloud, push-notification delivery at scale, store pricing, delivery ordering, multi-user households (all out of MVP per Manifest §4).

**Prerequisites:** Phases 1–9 complete and green. `data/samples/` directory exists (created in Phase 6 for vision fixtures — this phase extends it).

---

## File structure (locked in by this plan)

```text
backend/app/evaluation/
├── __init__.py
├── metrics.py           # §22 metric computations (extends Phase 6 vision metrics)
├── demo_flow.py         # scripted nine-step §27 run
├── test_ledger.py       # ledger metric suite (thresholds)
└── test_agents.py       # agent metric suite (thresholds)
scripts/
└── seed_demo_user.py
data/samples/
├── manifest.json        # sample → expected detections/OCR fields mapping
├── groceries/*.jpg      # post-shopping check-in photos
├── labels/*.jpg         # product label crops
└── receipts/*.jpg
tests/test_e2e_demo.py
documents/specs/evaluation-results.md   # filled with real numbers at the end
```

---

### Task 1: Demo user seed script (idempotent)

**Files:**
- Create: `scripts/seed_demo_user.py`
- Test: `tests/test_e2e_demo.py` (seed section)

- [ ] **Step 1: Write the failing test** —

```python
def test_seed_is_idempotent(db):
    seed_demo_user(db); first = snapshot_counts(db)
    seed_demo_user(db); second = snapshot_counts(db)
    assert first == second  # running twice creates nothing extra


def test_seed_profile_matches_demo_script(db):
    seed_demo_user(db)
    user = get_demo_user(db)
    assert "no beef" in user.dietary_restrictions
    assert user.cuisine_preferences[:1] == ["Indian"]
    assert user.protein_goal == "high"          # Manifest §27 step 1 persona
```

- [ ] **Step 2: Run to verify it fails** — `uv run pytest tests/test_e2e_demo.py -k seed -v` → FAIL (ImportError).

- [ ] **Step 3: Implement** — upsert-by-fixed-UUID: demo user (`no beef`, Indian-first, high protein, budget 60), a starter pantry (milk `1/2`, rice `3/4`, eggs 6, spinach expiring soon), one historical Fage review rule, frequent-item history (milk, bananas). Runnable standalone: `uv run python scripts/seed_demo_user.py`.

- [ ] **Step 4: Run to verify it passes.**

- [ ] **Step 5: Commit** — `feat(eval): idempotent demo user seed`

---

### Task 2: Sample data + expectations manifest

**Files:**
- Create: `data/samples/manifest.json`, `data/samples/{groceries,labels,receipts}/*.jpg`

- [ ] **Step 1: Curate samples** — 8–12 grocery check-in photos, 6+ label crops (at least one barcode-visible, one unreadable-brand for the needs-review path), 2 receipts. Sources: own photos or the Grocery Store / CORD datasets (Manifest §18.3–18.4). No personal data in frame.

- [ ] **Step 2: Write `manifest.json`** — one entry per image:

```json
{
  "image": "groceries/checkin_01.jpg",
  "expected_detections": [{"label": "milk carton", "count": 1}, {"label": "tomato", "count": 4}],
  "expected_ocr_fields": {"brand": "Chobani"},
  "expects_review_flag": false
}
```

- [ ] **Step 3: Verify** — a loader test asserts every listed file exists and every image file is listed (no orphans either way).

- [ ] **Step 4: Commit** — `feat(eval): sample images with expectations manifest`

---

### Task 3: Ledger metric suite

**Files:**
- Create: `backend/app/evaluation/metrics.py`, `backend/app/evaluation/test_ledger.py`

- [ ] **Step 1: Write the failing tests** — metrics from Manifest §22 with explicit thresholds:

```python
def test_checklist_to_ledger_correctness(db, demo_run):
    assert metrics.checklist_to_ledger_correctness(db) == 1.0   # every cross-off → exactly one item

def test_source_metadata_completeness(db, demo_run):
    assert metrics.source_metadata_completeness(db) == 1.0      # invariant 2: no unsourced field

def test_inventory_mutation_error_rate(db, demo_run):
    assert metrics.mutation_error_rate(db) == 0.0               # no write bypassed apply_update

def test_estimated_field_editability(db, demo_run):
    assert metrics.estimated_field_editability(db) == 1.0       # every estimate is editable
```

- [ ] **Step 2: Run to verify they fail** — FAIL (ImportError).

- [ ] **Step 3: Implement `metrics.py` ledger section** — computed from the change log + item table: cross-off events vs created items; fields with complete SourcedField metadata / total populated fields; change-log rows without source (must be zero); estimates with `editable: true`.

- [ ] **Step 4: Run to verify they pass** against a seeded demo run.

- [ ] **Step 5: Commit** — `feat(eval): ledger metric suite with hard thresholds`

---

### Task 4: Agent metric suite

**Files:**
- Create: `backend/app/evaluation/test_agents.py`
- Modify: `backend/app/evaluation/metrics.py`

- [ ] **Step 1: Write the failing tests** — routing/violation metrics over a fixed case set:

```python
ROUTING_CASES = [...]  # 20+ labeled inputs: text query, image, cross-off, ad-hoc update, recipe ask

def test_intent_routing_accuracy():
    assert metrics.routing_accuracy(ROUTING_CASES) >= 0.90

def test_dietary_violation_rate_is_zero(demo_run):
    assert metrics.dietary_violation_rate(demo_run.lists + demo_run.recipes) == 0.0

def test_recipe_availability_correctness(demo_run):
    assert metrics.recipe_availability_correctness(demo_run.recipes) == 1.0

def test_vague_usage_clarification_accuracy():
    assert metrics.clarification_accuracy(VAGUE_USAGE_CASES) == 1.0  # right scale per quantity type
```

- [ ] **Step 2: Run to verify they fail.**

- [ ] **Step 3: Implement** — routing accuracy over the labeled set (deterministic router path); violation rate scans generated lists/recipes against restrictions; availability correctness re-checks recommended recipes against the ledger snapshot; clarification accuracy asserts liquid/bulk → bucket scale, solids → count question.

- [ ] **Step 4: Run to verify they pass.** Vision metrics (Phase 6) + these two suites now run together: `uv run pytest backend/app/evaluation -v`.

- [ ] **Step 5: Commit** — `feat(eval): agent metric suite`

---

### Task 5: Scripted demo flow

**Files:**
- Create: `backend/app/evaluation/demo_flow.py`

- [ ] **Step 1: Implement `run_demo(client, db) -> DemoRun`** — executes Manifest §27 in order, collecting artifacts:

```text
1 plan list        POST /shopping-lists (high protein, Indian, no beef)
2 while shopping   POST /shopping/assist with yogurt photo (consent granted_for_session)
3 cross off        POST .../confirm for milk, tomatoes, rice, eggs, spinach
4 silent check-in  POST /check-in/groceries with sample photos
5 estimate review  confirm/edit flagged fields via pantry field actions
6 recipe ask       POST /recipes/recommend (dinner, 30 min, Indian)
7 consumption      POST /consumption/ad-hoc "I used a lot of milk" → answer 1/2
8 first-use review POST /reviews (yogurt "too sour", after_first_use=true)
9 next list        POST /shopping-lists → avoids Fage, suggests alternative
```

- [ ] **Step 2: Verify standalone** — `uv run python -m backend.app.evaluation.demo_flow` prints a step-by-step transcript ending `9/9 steps completed`.

- [ ] **Step 3: Commit** — `feat(eval): scripted nine-step demo flow`

---

### Task 6: The E2E test — nine steps + seven invariants

**Files:**
- Create: `tests/test_e2e_demo.py` (main section)

- [ ] **Step 1: Write the failing test** —

```python
def test_full_demo_holds_all_invariants(client, db):
    seed_demo_user(db)
    run = run_demo(client, db)

    assert run.completed_steps == 9

    # invariant checks across the entire run:
    assert metrics.mutation_error_rate(db) == 0.0            # 1: single write path
    assert metrics.source_metadata_completeness(db) == 1.0   # 2: every write sourced
    assert run.confirmed_field_overwrites == 0               # 3: estimates never beat user values
    assert run.images_without_consent == 0                   # 4: consent everywhere
    assert run.direct_llm_ledger_writes == 0                 # 5: proposals only
    assert run.strong_rules_before_first_use == 0            # 6: first-use gate
    assert run.deductions_outside_confirm_cooked == 0        # 7: no auto-deduct
```

- [ ] **Step 2: Run to verify it fails** (missing `run_demo` wiring / counters).

- [ ] **Step 3: Implement the counters on `DemoRun`** — derived from the change log, image table, and consumption events; no counter may be computed from "what the code intended," only from persisted state.

- [ ] **Step 4: Run to verify it passes** — `uv run pytest tests/test_e2e_demo.py -v`. Then run the whole suite: `uv run pytest` — everything from Phases 1–10 green.

- [ ] **Step 5: Commit** — `feat(eval): end-to-end demo test asserting all seven invariants`

---

### Task 7: Results write-up + demo assets

**Files:**
- Create: `documents/specs/evaluation-results.md`
- Modify: `README.md`

- [ ] **Step 1: Fill `evaluation-results.md`** — a table per §22 group (vision, ledger, agents, UX) with metric, threshold, measured value, and known gaps (e.g., OCR accuracy on glare-heavy labels).

- [ ] **Step 2: Write the demo README section + video script** — the nine steps with the exact taps/requests, ready to record; link from README.

- [ ] **Step 3: Verify** — every §22 metric appears either in the results table or in an explicit "not yet measured" list with a reason.

- [ ] **Step 4: Commit** — `docs(eval): evaluation results and demo script`

---

## Done criteria for Phase 10

- `uv run pytest` fully green across all phases, including the nine-step E2E demo with all seven invariant counters at their required values.
- Seed script idempotent; sample manifest complete (no orphan files or entries).
- Ledger and agent metric suites pass their thresholds; results published in `evaluation-results.md`.
- The demo is reproducible from a clean database: `docker compose up -d && uv run python scripts/seed_demo_user.py && uv run pytest tests/test_e2e_demo.py`.

## Post-MVP (next plans, written after this ships)

1. **Real auth** — swap the `get_current_user` placeholder for a real identity provider.
2. **Push notifications** — low-stock and use-soon reminders (mobile groundwork exists).
3. **Receipt-first enrichment** — receipt OCR as a primary evidence path (CORD-trained extraction).
4. **Store/Cost agent** — expense reports from receipt + manual prices (Manifest §15.16, deferred from MVP).
5. **Cloud deployment + CI/CD** — containerized backend + managed Postgres/Redis/S3; migration pipeline.
