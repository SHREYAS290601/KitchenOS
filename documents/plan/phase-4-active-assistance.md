# PantryOps Edge Phase 4: Active Assistance Implementation Plan

> **For agentic workers:** Implement task-by-task with strict TDD: write the failing test, watch it fail, implement, watch it pass, commit. Steps use checkbox (`- [ ]`) syntax. REQUIRED ECC SKILLS before starting: `/ecc:agent-harness-construction` (Input Router + While-Shopping Assistant + Auditor as testable agents with typed tool boundaries), `/ecc:security-review` (consent enforcement; user text and images are untrusted input), `/ecc:error-handling` (LLM/tool failure paths degrade, never crash the answer), `/ecc:react-native-patterns` (camera + accessible consent UI).

**Goal:** Handle the user's real-time requests — ad-hoc queries, while-shopping questions with optional photos, consent-gated image storage, the vague-usage quantity clarification flow — with Auditor v1 as the last gate on every answer.

**Architecture:** Per `documents/specs/architecture.md` §6–§8 (storage abstraction, agent layer, invariants 4–5) and `documents/specs/agents.md` §1, §4, §14, §19. First real LLM path: the assistant reads preferences/list/ledger and answers; it NEVER writes the ledger (no purchase was confirmed). Consent is captured with every image and enforced before storage (invariant 4). The LLM client sits behind one interface so tests inject a deterministic fake.

**Tech Stack:** unchanged backend stack + LLM SDK behind `agents/llm.py` (structured JSON output, Pydantic-validated), MinIO via the storage abstraction. Mobile: expo-camera, Expo + Jest + @testing-library/react-native.

**Out of scope for Phase 4** (later plans): real vision/OCR on the uploaded photos (Phase 6 — here they are stored evidence only), background job execution (Phase 5), product APIs (Phase 7), recipe answers (Phase 8 — the router recognizes the intent and returns a stub).

**Prerequisites:** Phase 3 complete; MinIO healthy in compose; an LLM API key in `.env` for the `-m integration` suite (unit tests use the fake).

---

## File structure (locked in by this plan)

```text
backend/app/
├── storage/
│   ├── __init__.py
│   ├── base.py                    # ObjectStore protocol: put/get_uri/delete/open
│   ├── local.py                   # filesystem impl (data/user_uploads/)
│   └── s3.py                      # MinIO/S3 impl
├── models/
│   ├── consent.py                 # per-user consent state
│   └── image_evidence.py          # ImageEvidenceRecord
├── schemas/
│   ├── consent.py
│   └── assist.py
├── services/
│   ├── consent.py                 # grant/revoke/check
│   └── image_storage.py           # store-with-consent, retention stamping
├── agents/
│   ├── llm.py                     # LLM client interface + fake for tests
│   ├── input_router.py
│   ├── while_shopping_assistant.py
│   ├── consumption_update.py
│   └── auditor.py                 # v1: consent, unsupported claims, confidence
└── routes/
    ├── images.py                  # POST /images (consent-gated)
    ├── assist.py                  # POST /shopping/assist
    └── consumption.py             # POST /consumption/ad-hoc
backend/alembic/versions/<images_consent>.py
tests/
├── test_storage.py
├── test_consent.py
├── test_image_storage.py
├── test_input_router.py
├── test_assist_api.py
├── test_consumption_flow.py
└── test_auditor.py
mobile/
├── screens/ConsentPrompt.tsx
├── screens/AssistScreen.tsx
├── camera/CaptureScreen.tsx
└── __tests__/{ConsentPrompt,AssistScreen}.test.tsx
```

---

### Task 1: Object-storage abstraction

**Files:**
- Create: `backend/app/storage/__init__.py`, `base.py`, `local.py`, `s3.py`
- Test: `tests/test_storage.py`

- [ ] **Step 1: Write the failing tests** — against both impls (local via `tmp_path`, MinIO marked `-m integration`): `put_image` returns an opaque URI; `open(uri)` round-trips bytes; `delete(uri)` then `open` raises `NotFound`; `get_uri` is stable. Backend selected from `Settings.storage_backend`.

- [ ] **Step 2: Run to verify they fail** — `uv run pytest tests/test_storage.py -v` → FAIL.

- [ ] **Step 3: Implement** — `base.py` protocol; `local.py` under `data/user_uploads/` with UUID names; `s3.py` via boto3 against MinIO; factory in `__init__.py`.

- [ ] **Step 4: Run to verify they pass. Commit** — `feat(storage): object-store abstraction with local and s3 backends`

---

### Task 2: Consent model + service (invariant 4, first half)

**Files:**
- Create: `backend/app/models/consent.py`, `backend/app/services/consent.py`, `backend/app/schemas/consent.py`, migration
- Test: `tests/test_consent.py`

- [ ] **Step 1: Write the failing tests** — the Manifest §8 state machine:

```python
def test_states_enumerated():          # not_requested, denied, granted_for_single_image,
                                       # granted_for_session, always_granted, revoked
def test_default_is_not_requested():
def test_storage_allowed_only_when_granted():
    # check_can_store(user, session) True only for granted_for_session (matching
    # session), always_granted, or an unconsumed granted_for_single_image
def test_single_image_grant_consumed_after_one_use():
def test_revoked_blocks_future_storage():
def test_session_grant_scoped_to_session():   # other session id → refused
```

- [ ] **Step 2: Run to verify they fail.**

- [ ] **Step 3: Implement** — consent rows per user (+ optional session scope), `services/consent.py::check_can_store()` as the single authority; `grant/revoke` update rows, single-image grants consumed atomically.

- [ ] **Step 4: Run to verify they pass. Commit** — `feat(consent): consent state machine with storage authority`

---

### Task 3: Image evidence records + consent-gated upload

**Files:**
- Create: `backend/app/models/image_evidence.py`, `backend/app/services/image_storage.py`, `backend/app/routes/images.py` (extend migration)
- Test: `tests/test_image_storage.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_upload_with_consent_stores_and_records():
    # POST /images (multipart + capture_context, session id) with granted consent
    # → 201; ImageEvidenceRecord has storage_uri, consent_status snapshot,
    #   retention_policy, capture_context
def test_upload_without_consent_403_and_no_bytes_stored():
    # object store empty; no ImageEvidenceRecord row
def test_no_image_row_without_consent_status():   # column nullable=False
def test_retention_policy_recorded_from_user_choice():
    # delete_after_answer | delete_after_enrichment | keep_for_pantry_memory |
    # keep_until_manually_deleted
```

- [ ] **Step 2: Run to verify they fail.**

- [ ] **Step 3: Implement** — `image_storage.py` asks `consent.check_can_store()` BEFORE touching the object store; record per `data-models.md` §4.5; 403 detail explains how to grant consent.

- [ ] **Step 4: Run to verify they pass. Commit** — `feat(images): consent-gated upload with evidence records`

---

### Task 4: LLM client interface + Input Router

**Files:**
- Create: `backend/app/agents/llm.py`, `backend/app/agents/input_router.py`
- Test: `tests/test_input_router.py`

- [ ] **Step 1: Write the failing tests** — with the fake LLM:

```python
def test_routes_shopping_question_to_assistant():   # "Should I buy this yogurt?" + image
def test_routes_vague_usage_to_consumption():       # "I used a lot of milk"
def test_routes_recipe_request_to_stub():           # "What can I cook?" → recipe intent (Phase 8)
def test_routes_checklist_action():                 # structured cross-off payload
def test_router_output_is_structured():             # normalized intent + agents + typed payload
def test_router_never_writes():                     # ledger boundary guard still green;
                                                    # router has no session dependency at all
```

- [ ] **Step 2: Run to verify they fail.**

- [ ] **Step 3: Implement** — `llm.py`: `LLMClient` protocol with `complete_structured(prompt, schema) -> BaseModel`, a real impl and `FakeLLM` (canned responses keyed by marker). `input_router.py`: intent classification via structured output, fallback keyword rules when the LLM call fails (`ecc:error-handling` — degraded, not dead). No DB session in its signature (Manifest §15.1 forbidden actions, structurally).

- [ ] **Step 4: Run to verify they pass. Commit** — `feat(agents): llm interface and input router with typed intents`

---

### Task 5: While-Shopping Assistant + /shopping/assist

**Files:**
- Create: `backend/app/agents/while_shopping_assistant.py`, `backend/app/schemas/assist.py`, `backend/app/routes/assist.py`
- Test: `tests/test_assist_api.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_assist_answers_from_preferences_and_ledger():
    # seeded dislike (sour yogurt, brand X) + question about that yogurt
    # → answer references the past dislike; applied preference ids listed
def test_assist_never_mutates_ledger():
    # before/after snapshot of pantry rows + change log identical
def test_assist_no_medical_claims():
    # fake LLM emits "this is safe for your allergy" → auditor blocks,
    # response degrades to restriction-neutral guidance (Guardrail 1/3)
def test_assist_no_identity_claim_without_evidence():
    # no OCR/barcode in context → answer marked "looks like", never exact identity
def test_assist_with_photo_stores_only_with_consent():
    # image_id linked when consented; stored_for_future_enrichment True (§6.6)
def test_assist_survives_llm_failure():   # LLM raises → 200 with fallback message, not 500
```

- [ ] **Step 2: Run to verify they fail.**

- [ ] **Step 3: Implement** — agent gathers context (list, ledger read-only, preferences, optional image record), calls the LLM for a structured answer, pipes through the Auditor (Task 7), returns advice + applied-preference ids. Route per `api-spec.md`.

- [ ] **Step 4: Run to verify they pass. Commit** — `feat(assist): while-shopping assistant with auditor-gated answers`

---

### Task 6: Vague-usage quantity flow

**Files:**
- Create: `backend/app/agents/consumption_update.py`, `backend/app/routes/consumption.py`
- Test: `tests/test_consumption_flow.py`

- [ ] **Step 1: Write the failing tests** — Manifest §6.4/§15.14: vague liquid ("used a lot of milk") → clarification with exactly `[Full] [3/4] [1/2] [1/4] [Empty]`; vague bulk (rice) → same buckets; vague countable (tomatoes) → "how many are left?" count question; explicit reply (`new_quantity_value: "1/2"`) → applied via `apply_update()` as `user_confirmed`; **no quantity change ever occurs on the vague message itself**; unknown item name → clarification asking which item, not a guess.

- [ ] **Step 2: Run to verify they fail.**

- [ ] **Step 3: Implement** — agent resolves the item, branches the question on `quantity_type` (buckets vs count — from Phase 2 vocabulary), returns a structured clarification; the explicit-reply path is the only one that touches the ledger.

- [ ] **Step 4: Run to verify they pass. Commit** — `feat(consumption): ask-don't-guess quantity clarification flow`

---

### Task 7: Auditor v1 (last gate)

**Files:**
- Create: `backend/app/agents/auditor.py`
- Modify: `backend/app/routes/assist.py` (already wired in Task 5 — this task hardens it)
- Test: `tests/test_auditor.py`

- [ ] **Step 1: Write the failing tests** — deterministic rule checks (no LLM):

```python
def test_blocks_processing_without_consent():      # proposal touching a non-consented image
def test_blocks_unsourced_claim():                 # answer asserting brand with no evidence field
def test_flags_low_confidence_shown_as_fact():     # confidence 0.4 rendered without "estimated"
def test_blocks_medical_or_safety_claims():        # "safe to eat" phrasing → blocked (Guardrail 1)
def test_pass_through_annotates_nothing_on_clean_output():
def test_verdicts_are_structured():                # AuditVerdict: pass | block | needs_review + reasons
```

- [ ] **Step 2: Run to verify they fail.**

- [ ] **Step 3: Implement** — pure functions over the structured answer + its evidence context; extensible check registry (Phases 7–9 add checks: unsourced enrichment, recipe availability, preference overgeneralization). Every user-facing agent response passes through `auditor.review()` before serialization.

- [ ] **Step 4: Run to verify they pass. Commit** — `feat(auditor): deterministic v1 gate on assist outputs`

---

### Task 8: Active-photo reuse linkage (§6.6)

**Files:**
- Modify: `backend/app/services/image_storage.py`, `backend/app/agents/while_shopping_assistant.py`
- Test: append to `tests/test_image_storage.py`

- [ ] **Step 1: Write the failing test** — a consented photo uploaded during an assist query gets `capture_context="while_shopping_query"`, `stored_for_future_enrichment=True`, `related_item_candidate` from the router intent, and `linked_shopping_session_id`; consent scope is snapshotted on the record (Phase 5 reads this — it never re-derives consent).

- [ ] **Step 2: Verify fail → implement → verify pass.**

- [ ] **Step 3: Commit** — `feat(images): active photos linked for future background enrichment`

---

### Task 9: Mobile — consent prompt, capture, assist chat (WCAG 2.1 AA)

**Files:**
- Create: `mobile/screens/ConsentPrompt.tsx`, `mobile/camera/CaptureScreen.tsx`, `mobile/screens/AssistScreen.tsx`
- Test: `mobile/__tests__/ConsentPrompt.test.tsx`, `mobile/__tests__/AssistScreen.test.tsx`

- [ ] **Step 1: Write the failing tests**

```tsx
// ConsentPrompt: the three §8 choices as a radiogroup — each option
// accessibilityRole "radio" with accessibilityState {checked} and a full-text
// label ("Yes, save for this shopping session"); nothing conveyed by color alone;
// selection reachable and confirmable via keyboard/switch access
// AssistScreen: question input has an accessible label; the answer region is
// accessibilityLiveRegion="polite"; "answer pending" announced as text;
// attached-photo state shows a labeled thumbnail with a remove button
```

- [ ] **Step 2: Run to verify they fail** — `npx jest mobile/__tests__ -t Consent` → FAIL.

- [ ] **Step 3: Implement** — `ConsentPrompt` fires before the FIRST photo action and whenever consent is `not_requested`/`revoked`; choice posts to the consent endpoint and is cached. `CaptureScreen` wraps expo-camera with a labeled shutter button and photo-review step. `AssistScreen` renders the chat flow, calls `/shopping/assist`, shows applied-preference context ("Avoiding brand X — you disliked it") as plain text.

- [ ] **Step 4: Run to verify they pass. Commit** — `feat(mobile): accessible consent, capture, and assist screens`

---

## Done criteria for Phase 4

- Assist endpoint answers from ledger + preferences and provably never mutates the ledger (snapshot test + boundary guard green).
- Images are stored only with consent — 403 leaves zero bytes and zero rows; every image row carries consent status and retention policy.
- Vague usage always yields the correct scale question for the item's quantity type; only an explicit user reply changes quantity, as `user_confirmed`.
- Auditor v1 blocks non-consented processing, unsourced claims, medical/safety phrasing, and low-confidence-as-fact — and is wired into every assist response.
- LLM failure degrades to a fallback answer (200), never a 500.
- Consent, capture, and assist screens pass accessibility tests (radiogroup semantics, live regions, text-conveyed state).

## Next phase

[Phase 5 — Silent Grocery Check-In](phase-5-silent-check-in.md): the durable BackgroundJob model, Celery pipeline skeleton with per-step status, and post-shopping multi-image upload.
