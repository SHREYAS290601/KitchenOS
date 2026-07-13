# PantryOps Edge Phase 3: Shopping Checklist Implementation Plan

> **For agentic workers:** Implement task-by-task with strict TDD: write the failing test, watch it fail, implement, watch it pass, commit. Steps use checkbox (`- [ ]`) syntax. REQUIRED ECC SKILLS before starting: `/ecc:fastapi-patterns` (shopping routers), `/ecc:python-testing` (checklist-to-ledger correctness tests), `/ecc:database-migrations` (shopping tables land with their models), `/ecc:react-testing` (accessible checklist screen + offline cache integration).

**Goal:** Implement grocery-list creation, item categorization, the cross-off flow producing purchase-confirmation events, and checklist-to-ledger insertion — the highest-trust purchase signal in the system, and the first real caller of `apply_update()`.

**Architecture:** Per `documents/specs/architecture.md` §9 and `documents/specs/data-models.md` §4.3–4.4. Cross-off is "very high" evidence but confirms ONLY that the planned item was bought — never brand, price, or size (Manifest §6.3, §15.3). New pantry items enter with `canonical_name` confident and everything else `unknown`. The Shopping Planner Agent ships here as a deterministic rule-based implementation; LLM wiring arrives in Phase 4 — but its forbidden-action tests are written now and survive the swap.

**Tech Stack:** unchanged from Phase 2 (FastAPI, SQLAlchemy 2.0, Alembic, pytest). Mobile: Expo + Jest + @testing-library/react-native, checklist cache from Phase 1.

**Out of scope for Phase 3** (later plans): LLM-quality list generation (Phase 4+), preference-rule filtering beyond the stub interface (Phase 9 wires real rules in), price/expense (Store/Cost agent, post-MVP §19 surface), image capture (Phase 4), receipts (Phase 6).

**Prerequisites:** Phase 2 complete — `apply_update()` green with the full evidence matrix; boundary guard passing.

---

## File structure (locked in by this plan)

```text
backend/app/
├── models/
│   ├── shopping_list.py           # ShoppingList
│   ├── shopping_item.py           # ShoppingItem (reason, priority, crossed_off)
│   └── confirmation_event.py      # ShoppingConfirmationEvent
├── schemas/
│   └── shopping.py                # list-create request, list/item/confirm responses
├── services/
│   ├── shopping.py                # list creation orchestration
│   └── checklist.py               # cross-off → event → ledger insertion
├── agents/
│   ├── __init__.py
│   ├── base.py                    # Agent protocol: run(context) -> proposal
│   ├── shopping_planner.py        # rule-based v1 (LLM swap later, same tests)
│   └── checklist_confirmation.py  # pantry-insertion proposal builder
└── routes/
    └── shopping.py                # POST /shopping-lists, POST .../confirm
backend/alembic/versions/<shopping_initial>.py
tests/
├── test_shopping_models.py
├── test_shopping_planner.py
├── test_shopping_api.py
├── test_checklist_confirm.py
└── test_checklist_to_ledger.py
mobile/
├── screens/ChecklistScreen.tsx
└── __tests__/ChecklistScreen.test.tsx
```

---

### Task 1: Shopping models

**Files:**
- Create: `backend/app/models/shopping_list.py`, `backend/app/models/shopping_item.py`, `backend/alembic/versions/<shopping_initial>.py`
- Test: `tests/test_shopping_models.py`

- [ ] **Step 1: Write the failing test** — round-trip a `ShoppingList` with two `ShoppingItem`s; assert every item requires `category`, `reason`, `priority` (nullable=False), `crossed_off` defaults False, `status` defaults `planned`, and `(shopping_list_id, canonical_name)` is unique (no duplicate planned items).

- [ ] **Step 2: Run to verify it fails** — `uv run pytest tests/test_shopping_models.py -v` → FAIL (ImportError).

- [ ] **Step 3: Implement the models** per `data-models.md` §4.3 — UUID PKs, `added_by` records the producing agent, `desired_quantity` + `unit_label` reuse the Phase 2 quantity vocabulary.

- [ ] **Step 4: Generate + hand-review the migration; `alembic upgrade head`; parity test green.**

- [ ] **Step 5: Run to verify it passes. Commit** — `feat(shopping): list and item models with reason and priority`

---

### Task 2: Confirmation event model

**Files:**
- Create: `backend/app/models/confirmation_event.py` (extend the migration)
- Test: append to `tests/test_shopping_models.py`

- [ ] **Step 1: Write the failing test** — insert a `ShoppingConfirmationEvent` per `data-models.md` §4.4; assert `confirmation_source` fixed to `checklist_cross_off`, `confidence == 1.0`, and a unique constraint on `shopping_item_id` (an item can be confirmed once — the API turns the second attempt into a 409).

- [ ] **Step 2: Verify fail → implement → verify pass.**

- [ ] **Step 3: Commit** — `feat(shopping): purchase confirmation event model`

---

### Task 3: Agent protocol + rule-based Shopping Planner

**Files:**
- Create: `backend/app/agents/__init__.py`, `backend/app/agents/base.py`, `backend/app/agents/shopping_planner.py`
- Test: `tests/test_shopping_planner.py`

- [ ] **Step 1: Write the failing tests** — these encode Manifest §15.2 forbidden actions and survive the Phase-4+ LLM swap unchanged:

```python
def test_planner_returns_categorized_items_with_reasons():
    # given a ledger with low milk (capacity 1/4) and a frequent-item history,
    # proposal contains milk under "frequent restocks" with a non-empty reason
def test_planner_never_emits_restricted_items():
    # restrictions=["no beef"] → no item whose canonical_name/category matches beef
def test_planner_respects_strong_negative_preference():
    # a strong avoid rule for brand X on yogurt → yogurt suggestion carries
    # an alternative, never brand X
def test_planner_never_marks_items_bought():
    # proposal items all have status "planned", crossed_off False
```

- [ ] **Step 2: Run to verify they fail** — FAIL (ImportError).

- [ ] **Step 3: Implement** — `base.py` defines the `Agent` protocol (`run(context) -> proposal`, Pydantic in/out — spec `agents.md` preamble). `shopping_planner.py` v1 is deterministic: low-stock scan (capacity ≤ 1/4 or count ≤ threshold), frequent-item history, restriction filter (substring + category match), preference-rule hook accepting an injected list (Phase 9 supplies real rules).

- [ ] **Step 4: Run to verify they pass.**

- [ ] **Step 5: Commit** — `feat(agents): agent protocol and rule-based shopping planner`

---

### Task 4: Create-list endpoint

**Files:**
- Create: `backend/app/schemas/shopping.py`, `backend/app/routes/shopping.py`, `backend/app/services/shopping.py`
- Modify: `backend/app/main.py`
- Test: `tests/test_shopping_api.py`

- [ ] **Step 1: Write the failing tests** — `POST /shopping-lists` with the `api-spec.md` request body (goal, cuisine_preferences, dietary_restrictions, protein_goal, budget) returns 201 with a persisted, categorized list; every item has `reason` and `priority`; a request with `dietary_restrictions: ["no beef"]` yields a list where no item matches beef (API-level restatement of the planner test — this guards the wiring, not just the agent).

- [ ] **Step 2: Run to verify they fail** — 404.

- [ ] **Step 3: Implement** — route validates via `schemas/shopping.py`, `services/shopping.py` calls the planner, persists list + items, returns the serialized list.

- [ ] **Step 4: Run to verify they pass. Commit** — `feat(shopping): create-list endpoint backed by the planner`

---

### Task 5: Cross-off confirmation

**Files:**
- Create: `backend/app/services/checklist.py`, `backend/app/agents/checklist_confirmation.py`
- Modify: `backend/app/routes/shopping.py`
- Test: `tests/test_checklist_confirm.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_confirm_creates_event_and_marks_item():
    # POST /shopping-lists/{list}/items/{item}/confirm {"status": "bought"}
    # → 200, event with confirmation_source=checklist_cross_off, confidence 1.0,
    #   shopping item status "bought", crossed_off True
def test_double_confirm_409():
def test_confirm_missing_item_404():
def test_agent_proposal_never_infers_details():
    # checklist_confirmation proposal: canonical_name sourced checklist_cross_off,
    # brand/product_name/quantity beyond default all ABSENT from the proposal
```

- [ ] **Step 2: Run to verify they fail.**

- [ ] **Step 3: Implement** — `agents/checklist_confirmation.py` builds the pantry-insertion proposal (Manifest §15.3: never brand, never price, never size); `services/checklist.py` writes the event and item status in one transaction; route returns event + (in Task 6) the new pantry id.

- [ ] **Step 4: Run to verify they pass. Commit** — `feat(checklist): cross-off confirmation events`

---

### Task 6: Checklist-to-ledger insertion (the first real apply_update caller)

**Files:**
- Modify: `backend/app/services/checklist.py`
- Test: `tests/test_checklist_to_ledger.py`

- [ ] **Step 1: Write the failing tests** — the §22 "checklist-to-ledger correctness" metric as tests:

```python
def test_confirm_inserts_pantry_item_via_ledger():
    # after confirm: pantry item exists; canonical_name.status == user_confirmed,
    # canonical_name.source == checklist_cross_off, confidence == 1.0;
    # brand.status == unknown; quantity_value.source == checklist_default,
    # quantity_value.status == estimated; lifecycle status == "bought"
def test_confirm_writes_change_log_rows():
    # one log row per initialized field, all sourced
def test_confirm_links_source_event():
    # pantry_item.source_event_id == the confirmation event id
def test_no_direct_orm_writes():
    # boundary guard from Phase 2 still green with checklist.py in the tree
```

- [ ] **Step 2: Run to verify they fail.**

- [ ] **Step 3: Implement** — `checklist.py` maps the agent proposal to `apply_update()` calls (creation path: unknown-status fields skipped, not written as empty estimates). The event, item status, pantry insertion, and change log all commit in one transaction.

- [ ] **Step 4: Run to verify they pass. Commit** — `feat(checklist): checklist-to-ledger insertion through apply_update`

---

### Task 7: Mobile checklist screen (offline-capable, accessible)

**Files:**
- Create: `mobile/screens/ChecklistScreen.tsx`
- Modify: `mobile/api/client.ts` (confirm call), `mobile/storage/checklistCache.ts` (pending-sync queue)
- Test: `mobile/__tests__/ChecklistScreen.test.tsx`

- [ ] **Step 1: Write the failing tests**

```tsx
it("renders items grouped by category with accessible checkboxes", ...)
   // each row: accessibilityRole "checkbox", accessibilityState {checked},
   // accessibilityLabel naming the item ("Cross off milk")
it("cross-off while offline queues and survives reload", ...)
   // fetch rejected → item shows "pending sync" as TEXT (not color), cache holds the queue
it("syncs queued cross-offs when back online", ...)
it("crossed-off items remain readable", ...)  // strikethrough + explicit "bought" text
```

- [ ] **Step 2: Run to verify they fail** — `npx jest mobile/__tests__/ChecklistScreen.test.tsx` → FAIL.

- [ ] **Step 3: Implement** — screen reads the Phase 1 cache first (works in-store with no signal), renders category sections with header roles, cross-off calls the confirm endpoint, failures enqueue into the cache's pending-sync queue and replay on reconnect. All state changes announced via `accessibilityLiveRegion="polite"`.

- [ ] **Step 4: Run to verify they pass. Commit** — `feat(mobile): offline-capable accessible checklist with cross-off sync`

---

## Done criteria for Phase 3

- Create list → cross off → pantry item appears via `apply_update()` with `canonical_name` user-confirmed, brand/size/price `unknown`, and a linked confirmation event — the full §22 checklist-to-ledger correctness path under test.
- Planner provably never emits restricted items, never overrides strong negative preferences, never marks items bought — at both agent and API level.
- Double-confirm is a 409; the Phase 2 boundary guard still passes.
- Mobile checklist works offline, queues cross-offs, and passes accessibility assertions (named checkboxes, text-conveyed state, live-region announcements).

## Next phase

[Phase 4 — Active Assistance](phase-4-active-assistance.md): the Input Router, While-Shopping Assistant, consent-gated photo storage, the vague-usage quantity flow, and Auditor v1.
