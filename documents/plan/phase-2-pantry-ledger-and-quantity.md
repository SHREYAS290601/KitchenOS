# PantryOps Edge Phase 2: Pantry Ledger and Quantity System Implementation Plan

> **For agentic workers:** Implement task-by-task with strict TDD: write the failing test, watch it fail, implement, watch it pass, commit. Steps use checkbox (`- [ ]`) syntax. REQUIRED ECC SKILLS before starting: `/ecc:tdd-guide` (this is the invariant-critical phase — nothing lands untested), `/ecc:python-patterns` (SourcedField generics, precedence function), `/ecc:postgres-patterns` (JSONB sourced fields + append-only change log), `/ecc:python-testing` (evidence-hierarchy matrix + boundary guard test), `/ecc:backend-patterns` (single-write-path service layering).

**Goal:** Implement the pantry-item model with field-level source metadata, the fail-safe quantity system, the single ledger write path enforcing the evidence hierarchy, the user-edit flow, and an append-only change log — the structural heart of the product that every later phase calls.

**Architecture:** Per `documents/specs/architecture.md` §8–§9 (invariants 1–3, precedence function) and `documents/specs/data-models.md` §1–§4. `services/ledger.py::apply_update()` becomes the ONLY pantry write path. SourcedField is one reusable Pydantic model. Quantity validation lives in `pantry/quantity.py`. Every applied write appends a `ledger_change_log` row in the same transaction.

**Tech Stack:** Python 3.12, SQLAlchemy 2.0 (JSONB columns via `sqlalchemy.dialects.postgresql`), Pydantic v2, Alembic, pytest + httpx TestClient against local Postgres (Phase 1 conftest).

**Out of scope for Phase 2** (later plans): shopping lists and cross-off (Phase 3), images/consent (Phase 4), background jobs (Phase 5), vision (Phase 6), enrichment (Phase 7), recipes/consumption events (Phase 8), preference rules (Phase 9). Those phases *call* `apply_update`; they do not extend it.

**Prerequisites:** Phase 1 complete — compose stack healthy, `uv run pytest` green, Alembic parity test passing.

---

## File structure (locked in by this plan)

```text
backend/app/
├── schemas/
│   ├── __init__.py
│   └── sourced_field.py           # SourcedField + FieldStatus + EvidenceSource
├── pantry/
│   ├── __init__.py
│   ├── quantity.py                # QuantityType, bucket/count validators
│   └── lifecycle.py               # lifecycle states + allowed transitions
├── models/
│   ├── __init__.py
│   ├── pantry_item.py             # JSONB sourced fields + quantity + lifecycle
│   └── ledger_change_log.py       # append-only audit rows
├── services/
│   ├── __init__.py
│   └── ledger.py                  # apply_update() — THE write path
└── routes/
    └── pantry.py                  # item CRUD + quantity + field actions
backend/alembic/versions/<pantry_initial>.py
tests/
├── test_sourced_field.py
├── test_quantity.py
├── test_lifecycle.py
├── test_ledger_service.py
├── test_pantry_api.py
├── test_change_log.py
└── test_ledger_boundary.py        # import/AST guard — invariant 1
```

One responsibility per file. No module outside `services/ledger.py` mutates pantry sourced fields — Task 8 makes that a failing test, not a convention.

---

### Task 1: SourcedField schema

**Files:**
- Create: `backend/app/schemas/__init__.py`, `backend/app/schemas/sourced_field.py`
- Test: `tests/test_sourced_field.py`

- [ ] **Step 1: Write the failing test** — `tests/test_sourced_field.py`

```python
import pytest
from pydantic import ValidationError

from backend.app.schemas.sourced_field import EvidenceSource, FieldStatus, SourcedField


def test_sourced_field_requires_provenance():
    f = SourcedField(value="Chobani", source=EvidenceSource.label_ocr, confidence=0.84, status=FieldStatus.estimated)
    assert f.editable is True


def test_missing_source_rejected():
    with pytest.raises(ValidationError):
        SourcedField(value="Chobani", confidence=0.84, status=FieldStatus.estimated)


def test_unknown_status_allows_null_value_and_confidence():
    f = SourcedField(value=None, source=EvidenceSource.none, confidence=None, status=FieldStatus.unknown)
    assert f.value is None


def test_confidence_bounds():
    with pytest.raises(ValidationError):
        SourcedField(value="x", source=EvidenceSource.label_ocr, confidence=1.3, status=FieldStatus.estimated)
```

- [ ] **Step 2: Run to verify it fails** — `uv run pytest tests/test_sourced_field.py -v` → FAIL (ImportError).

- [ ] **Step 3: Write `backend/app/schemas/sourced_field.py`**

```python
from datetime import datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, Field


class FieldStatus(StrEnum):
    estimated = "estimated"
    user_confirmed = "user_confirmed"
    user_edited = "user_edited"
    rejected = "rejected"
    unknown = "unknown"
    conflicting = "conflicting"


class EvidenceSource(StrEnum):
    """Ordered by trust — index in PRECEDENCE decides who wins (spec architecture.md §9)."""
    user_edited = "user_edited"
    user_confirmed = "user_confirmed"
    checklist_cross_off = "checklist_cross_off"
    barcode = "barcode"
    receipt_ocr = "receipt_ocr"
    label_ocr = "label_ocr"
    product_detection = "product_detection"
    segmentation = "segmentation"
    silent_check_in = "silent_check_in"
    api_enrichment = "api_enrichment"
    web_enrichment = "web_enrichment"
    llm_inference = "llm_inference"   # never a truth source
    none = "none"                     # for status=unknown placeholders


PRECEDENCE: list[EvidenceSource] = list(EvidenceSource)  # lower index = higher trust


class SourcedField(BaseModel):
    """Every provenance-carrying value in the system. source/confidence/status are
    REQUIRED — an unsourced write cannot even be constructed (invariant 2)."""

    value: object | None
    source: EvidenceSource
    confidence: float | None = Field(ge=0.0, le=1.0)
    status: FieldStatus
    editable: bool = True
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
```

- [ ] **Step 4: Run to verify it passes** — 4 PASS.

- [ ] **Step 5: Commit** — `feat(ledger): sourced-field schema with required provenance`

---

### Task 2: Quantity validators

**Files:**
- Create: `backend/app/pantry/__init__.py`, `backend/app/pantry/quantity.py`
- Test: `tests/test_quantity.py`

- [ ] **Step 1: Write the failing tests** — cover the full matrix from `data-models.md` §2:

```python
def test_capacity_bucket_accepts_only_allowed_values():   # full, 3/4, 1/2, 1/4, empty, unknown
def test_capacity_bucket_rejects_arbitrary_fraction():    # "2/3" → QuantityError
def test_count_accepts_non_negative_int():                # 3 tomatoes OK, -1 → QuantityError
def test_count_rejects_bucket_value():                    # "1/2" for a count item → QuantityError
def test_unknown_quantity_sets_needs_user_confirmation(): # value None + flag True
def test_unit_labels_for_counts():                        # piece/pack/box/dozen accepted
```

- [ ] **Step 2: Run to verify they fail** — `uv run pytest tests/test_quantity.py -v` → FAIL.

- [ ] **Step 3: Implement `quantity.py`** — `QuantityType` StrEnum (`count`, `capacity_bucket`, `unknown`); `CAPACITY_BUCKETS = ("full", "3/4", "1/2", "1/4", "empty", "unknown")`; `validate_quantity(quantity_type, value) -> ValidatedQuantity` raising `QuantityError` with a message that names the field and the allowed values (error messages must say how to fix — org standard).

- [ ] **Step 4: Run to verify they pass** — 6 PASS.

- [ ] **Step 5: Commit** — `feat(pantry): fail-safe quantity validators (count, capacity buckets, unknown)`

---

### Task 3: Lifecycle transitions

**Files:**
- Create: `backend/app/pantry/lifecycle.py`
- Test: `tests/test_lifecycle.py`

- [ ] **Step 1: Write the failing tests** — `advance(current, target)` allows the Manifest §12 forward path (`planned → bought → estimated → enriched → stored → opened → partially_used → low_quantity → used_up → reorder_candidate → archived`) plus side states (`expired_or_discarded`, `review_eligible`, `reviewed`); rejects illegal jumps (e.g. `planned → used_up`) with `LifecycleError`.

- [ ] **Step 2: Verify fail → implement** — a `TRANSITIONS: dict[str, set[str]]` table, not conditionals; the test asserts every §12 state appears as a key.

- [ ] **Step 3: Verify pass. Commit** — `feat(pantry): item lifecycle state machine`

---

### Task 4: PantryItem + LedgerChangeLog models

**Files:**
- Create: `backend/app/models/__init__.py`, `backend/app/models/pantry_item.py`, `backend/app/models/ledger_change_log.py`, `backend/alembic/versions/<pantry_initial>.py`
- Test: `tests/test_change_log.py` (model round-trip half)

- [ ] **Step 1: Write the failing test** — round-trip a `PantryItem` with JSONB sourced fields (`canonical_name`, `brand`, `quantity_value` as SourcedField dicts) and a `LedgerChangeLog` row; assert JSONB survives intact and `change_log` has no update path (attempting `session.delete(row)` on a log row raises via a `before_delete` event or DB rule).

- [ ] **Step 2: Run to verify it fails** — FAIL (ImportError).

- [ ] **Step 3: Implement the models** — `pantry_item` per `data-models.md` §4.1 (UUID PK, user_id, six SourcedField JSONB columns, `quantity_type`, `unit_label`, `purchase_date`, `storage_location`, `estimated_use_by`, lifecycle `status`, `source_event_id`, `needs_user_review`, timestamps). `ledger_change_log` per §4.2: `id, pantry_item_id, field_name, old_value JSONB, new_value JSONB, source, confidence, actor, created_at` — insert-only (SQLAlchemy `before_update`/`before_delete` listeners raise).

- [ ] **Step 4: Generate + hand-review the migration** — `uv run alembic revision --autogenerate -m "pantry ledger initial"`; check JSONB defaults and the change-log constraints survived autogenerate; `uv run alembic upgrade head`; parity test from Phase 1 still green.

- [ ] **Step 5: Run to verify it passes. Commit** — `feat(ledger): pantry item and append-only change log models`

---

### Task 5: apply_update() — the single write path

**Files:**
- Create: `backend/app/services/__init__.py`, `backend/app/services/ledger.py`
- Test: `tests/test_ledger_service.py`

- [ ] **Step 1: Write the failing tests** — the evidence-hierarchy matrix. Key cases:

```python
def test_estimate_fills_unknown_field():                  # label_ocr onto unknown → applied
def test_user_edit_beats_any_estimate():                  # user_edited over barcode → applied
def test_estimate_never_overwrites_user_confirmed():      # label_ocr onto user_confirmed
    # → NOT applied; stored status becomes/remains authoritative;
    #   incoming recorded as conflicting candidate; item.needs_user_review = True
def test_barcode_beats_label_ocr():                       # applied
def test_label_ocr_does_not_beat_barcode():               # rejected as lower precedence
def test_llm_inference_never_applies():                   # LedgerError — not a truth source
def test_unsourced_update_rejected():                     # dict missing source → LedgerError
def test_every_applied_update_writes_exactly_one_log_row()
def test_rejected_update_writes_no_log_row_but_records_conflict()
def test_quantity_update_validates_against_quantity_type()  # bucket value on count item → QuantityError
```

- [ ] **Step 2: Run to verify they fail** — `uv run pytest tests/test_ledger_service.py -v` → FAIL.

- [ ] **Step 3: Implement `services/ledger.py`**

```python
def apply_update(session: Session, item: PantryItem, field_name: str,
                 incoming: SourcedField, *, actor: str) -> ApplyResult:
    """THE pantry write path (invariants 1-3, spec architecture.md §8-§9).

    Applies `incoming` iff precedence(incoming.source) is at least as trusted as
    the stored field's source AND the stored status is not user_confirmed/user_edited
    (unless incoming is itself a user action). Otherwise records a conflict.
    Every applied change writes a ledger_change_log row in the same transaction.
    """
```

Precedence = index into `PRECEDENCE` (Task 1). `llm_inference` and `none` are rejected outright as write sources. Quantity fields route through `validate_quantity` first. Returns `ApplyResult(applied | conflict | rejected, log_row_id)`.

- [ ] **Step 4: Run to verify they pass** — full matrix PASS.

- [ ] **Step 5: Commit** — `feat(ledger): apply_update with evidence-hierarchy precedence and change log`

---

### Task 6: Pantry routes (item CRUD, quantity, field actions)

**Files:**
- Create: `backend/app/routes/pantry.py`
- Modify: `backend/app/main.py` (include router)
- Test: `tests/test_pantry_api.py`

- [ ] **Step 1: Write the failing tests** — per `api-spec.md`: `GET /pantry/items` (filter by lifecycle status), `GET /pantry/items/{id}` returns full SourcedField metadata, `POST /pantry/items/{id}/quantity` (§19.6 — 422 on a bucket value for a count item, applied value has `status=user_confirmed`), `POST /pantry/items/{id}/fields/{field}` with `confirm | edit | reject | leave_as_estimate`; the critical sequence test: user edits brand → later estimate call for brand → GET shows the user's value and a `conflicting` candidate, never the estimate.

- [ ] **Step 2: Run to verify they fail** — 404s (routes absent).

- [ ] **Step 3: Implement** — thin router delegating to `services/ledger.py`; user actions map to `EvidenceSource.user_edited/user_confirmed`; responses serialize SourcedFields verbatim (estimates are never hidden — Guardrail 8).

- [ ] **Step 4: Run to verify they pass.**

- [ ] **Step 5: Commit** — `feat(pantry): item routes with quantity and field confirm/edit/reject`

---

### Task 7: Mobile edit flow (per-field confirm/edit/reject)

**Files:**
- Create: `mobile/screens/PantryItemScreen.tsx`, `mobile/components/EstimatedField.tsx`
- Test: `mobile/__tests__/EstimatedField.test.tsx`

- [ ] **Step 1: Write the failing test** — `EstimatedField` renders value + source + confidence as text ("Brand: Chobani — Label OCR, 84%"), exposes Confirm / Edit / Reject / Leave-as-estimate as real buttons with `accessibilityLabel`s naming the field ("Confirm brand Chobani"), and estimated status is conveyed by text, never color alone.

- [ ] **Step 2: Verify fail → implement** — component + screen calling the field-action endpoint via the typed client; optimistic update rolls back on error with the error message naming the field.

- [ ] **Step 3: Verify pass** — `npx jest mobile/__tests__/EstimatedField.test.tsx` → PASS.

- [ ] **Step 4: Commit** — `feat(mobile): accessible per-field estimate review component`

---

### Task 8: Ledger boundary guard (invariant 1 as a test)

**Files:**
- Test: `tests/test_ledger_boundary.py`

- [ ] **Step 1: Write the guard test** — walk `backend/app/` with `ast`; assert that outside `services/ledger.py` and `models/`, no module assigns to a PantryItem sourced-field attribute or constructs `LedgerChangeLog` directly (allow-list: `services/ledger.py`, migrations, tests). Also assert `routes/pantry.py` imports `apply_update` and not the ORM write helpers.

- [ ] **Step 2: Prove it bites** — temporarily add a direct `item.brand = {...}` mutation in a route, run, see FAIL, revert. Do not commit the temporary change.

- [ ] **Step 3: Verify pass. Commit** — `test(ledger): AST boundary guard enforcing the single write path`

---

## Done criteria for Phase 2

- `uv run pytest` green across sourced-field, quantity, lifecycle, ledger matrix, pantry API, change log, and boundary guard.
- The full evidence-hierarchy matrix passes: user edit beats everything; estimates never overwrite `user_confirmed`/`user_edited` (stored as `conflicting` + `needs_user_review`); `llm_inference` can never write.
- Every applied write produces exactly one sourced change-log row; unsourced updates cannot be constructed.
- Quantity endpoints enforce exact allowed bucket values per quantity type.
- Mobile per-field review component is accessible (named actions, text-conveyed status) and tested.

## Next phase

[Phase 3 — Shopping Checklist](phase-3-shopping-checklist.md): shopping lists, cross-off confirmation events, and the first real writes through `apply_update()`.
