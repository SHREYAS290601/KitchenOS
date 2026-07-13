# PantryOps Edge — Data Model Specification

Canonical definitions for every persisted entity. Derived from `Manifest.md` §10–§14. Plan documents cite this file; the ORM in `backend/app/models/` and the Pydantic schemas in `backend/app/schemas/` must match it.

---

## 1. SourcedField — the core shape

Every value produced by OCR, detection, segmentation, barcode, API lookup, or web enrichment is an **estimate** unless user-confirmed. Each provenance-carrying field is stored as this JSONB object:

```json
{
  "value": "Chobani",
  "source": "label_ocr",
  "confidence": 0.84,
  "status": "estimated",
  "editable": true,
  "last_updated": "timestamp"
}
```

- `source` — one of the evidence sources in `architecture.md` §9 (precedence order).
- `confidence` — float 0–1, or null when status is `unknown`.
- `status` — see Field Status below.
- `editable` — always true for estimate-capable fields.

Implemented once as a generic Pydantic model in `backend/app/schemas/sourced_field.py`; `source`, `confidence`, `status` are **required** — a field change without them is rejected at the schema layer (invariant 2).

### Field status values

```text
estimated | user_confirmed | user_edited | rejected | unknown | conflicting
```

### User actions per estimated field

```text
confirm | edit | reject | leave_as_estimate
```

---

## 2. Quantity system

Fail-safe, coarse, user-correctable. Never pretend to know exact quantities. Validators live in `backend/app/pantry/quantity.py`.

| Quantity type | Applies to | Allowed values |
| ------------- | ---------- | -------------- |
| `count` | countable solids, packaged units | non-negative integer + unit label |
| `capacity_bucket` | liquids, bulk solids | `full`, `3/4`, `1/2`, `1/4`, `empty`, `unknown` |
| `unknown` | anything uncertain | `null` + `needs_user_confirmation: true` |

Unit labels for counts: `count, piece, block, pack, box, bag, loaf, bunch, container, tray, dozen` (plus item-specific labels like `tomatoes`, `bars`).

Examples:

```json
{ "canonical_name": "tomatoes", "quantity_type": "count", "quantity_value": 3, "unit_label": "tomatoes", "status": "user_confirmed" }
```

```json
{ "canonical_name": "rice", "quantity_type": "capacity_bucket", "quantity_value": "3/4", "unit_label": "bag", "status": "estimated" }
```

Vague usage ("I used a lot of milk") never guesses — the system asks with the correct scale for the item's quantity type.

---

## 3. Item lifecycle

Allowed states (transitions enforced in `backend/app/pantry/lifecycle.py`):

```text
planned → bought → estimated → enriched → stored → opened →
partially_used → low_quantity → used_up → reorder_candidate → archived
```

Side states: `expired_or_discarded`, `review_eligible`, `reviewed`. Illegal transitions are rejected.

---

## 4. Entities

### 4.1 PantryItem (`models/pantry_item.py`)

The ledger row. SourcedField JSONB columns marked (SF).

| Column | Type | Notes |
| ------ | ---- | ----- |
| `pantry_item_id` | UUID PK | |
| `user_id` | UUID FK | |
| `canonical_name` | JSONB (SF) | e.g. "milk"; source `checklist`, confidence 1.0 when from cross-off |
| `display_name` | JSONB (SF) | e.g. "Organic Whole Milk" from label OCR |
| `category` | JSONB (SF) | e.g. "dairy" |
| `brand` | JSONB (SF) | `unknown` until OCR/barcode/user provides it |
| `product_name` | JSONB (SF) | |
| `quantity_type` | text enum | `count` \| `capacity_bucket` \| `unknown` |
| `quantity_value` | JSONB (SF) | value validated against quantity_type |
| `unit_label` | text | |
| `purchase_date` | date | |
| `storage_location` | text | fridge / pantry / freezer |
| `estimated_use_by` | date, nullable | only when a date label was read |
| `status` | text enum | lifecycle state (§3) |
| `source_event_id` | UUID | the confirmation event that created it |
| `needs_user_review` | bool | |
| `created_at` / `updated_at` | timestamptz | |

### 4.2 LedgerChangeLog (`models/ledger_change_log.py`)

Append-only. One row per applied field change, written in the same transaction by `apply_update()`.

```text
id, pantry_item_id, field_name, old_value (JSONB), new_value (JSONB),
source, confidence, actor (user | agent | worker), created_at
```

Insert-only: no UPDATE or DELETE path.

### 4.3 ShoppingList / ShoppingItem (`models/shopping_list.py`, `shopping_item.py`)

```json
{
  "shopping_item_id": "shop_001",
  "shopping_list_id": "list_001",
  "canonical_name": "tomatoes",
  "category": "produce",
  "desired_quantity": 4,
  "unit_label": "tomatoes",
  "reason": "needed for planned recipes",
  "priority": "high",
  "status": "planned",
  "crossed_off": false,
  "added_by": "shopping_planner_agent",
  "created_at": "timestamp"
}
```

Every generated item carries a `reason` and `priority`.

### 4.4 ShoppingConfirmationEvent (`models/confirmation_event.py`)

```json
{
  "event_id": "confirm_001",
  "shopping_item_id": "shop_001",
  "canonical_name": "tomatoes",
  "status": "bought",
  "confirmation_source": "checklist_cross_off",
  "confidence": 1.0,
  "timestamp": "timestamp"
}
```

Cross-off confirms **purchase only** — never brand, price, size, or nutrition. The pantry item it creates has `canonical_name.status = user_confirmed` and everything else `unknown`.

### 4.5 ImageEvidenceRecord (`models/image_evidence.py`)

```json
{
  "image_id": "img_001",
  "user_id": "user_001",
  "capture_context": "post_shopping_check_in | while_shopping_query | label_scan | receipt",
  "processing_mode": "silent_background_enrichment | active_then_background_enrichment",
  "linked_shopping_session_id": "session_001",
  "related_item_candidate": null,
  "storage_uri": "s3://bucket/img_001.jpg",
  "consent_status": "granted_for_session",
  "retention_policy": "delete_after_enrichment",
  "stored_for_future_enrichment": true,
  "created_at": "timestamp"
}
```

Consent states: `not_requested | denied | granted_for_single_image | granted_for_session | always_granted | revoked`.
Retention policies: `delete_after_answer | delete_after_enrichment | keep_for_pantry_memory | keep_until_manually_deleted`.
No image row may exist without a consent status (invariant 4).

### 4.6 VisionDetection (`models/vision_detection.py`)

```json
{ "detection_id": "det_001", "image_id": "img_001", "label": "tomato",
  "bbox": [120, 80, 210, 190], "confidence": 0.86,
  "model_name": "grocery_detector_v1", "created_at": "timestamp" }
```

Category/count evidence only — never brand identity.

### 4.7 SegmentationResult (`models/segmentation_result.py`)

```json
{ "segmentation_id": "seg_001", "image_id": "img_001", "detection_id": "det_001",
  "mask_uri": "s3://bucket/masks/seg_001.png",
  "crop_uri": "s3://bucket/crops/item_001.png", "confidence": 0.81 }
```

### 4.8 OCRResult (`models/ocr_result.py`)

```json
{ "ocr_id": "ocr_001", "image_id": "img_001", "crop_uri": "s3://bucket/crops/item_001.png",
  "raw_text": "CHOBANI GREEK YOGURT 32 OZ",
  "structured_fields": { "brand": "Chobani", "product_name": "Greek Yogurt", "package_size": "32 oz" },
  "confidence": 0.84, "engine": "paddleocr", "created_at": "timestamp" }
```

Structured fields are candidates — they enter the ledger as estimates via Source Attribution, never as confirmed values.

### 4.9 ProductEnrichmentRecord (`models/product_enrichment.py`)

Per-field sourced enrichment from Open Food Facts / USDA:

```json
{ "enrichment_id": "enrich_001", "pantry_item_id": "item_001", "barcode": null,
  "brand":        { "value": "Chobani", "source": "label_ocr", "confidence": 0.84, "status": "estimated" },
  "product_name": { "value": "Greek Yogurt", "source": "label_ocr", "confidence": 0.78, "status": "estimated" },
  "nutrition_source": "open_food_facts_or_usda",
  "dietary_info_source": "api_enrichment", "created_at": "timestamp" }
```

External API responses are untrusted input: validated and sanitized before use; a match requires a reliable key (barcode first, confident OCR name second) or it returns "no match" — never a guess.

### 4.10 ConsumptionEvent (`models/consumption_event.py`)

```json
{ "consumption_id": "consume_001", "timestamp": "timestamp",
  "source": "user_message | recipe_confirmation",
  "items_used": [
    { "pantry_item_id": "item_egg", "canonical_name": "eggs", "amount_used": 2, "unit_label": "eggs" },
    { "pantry_item_id": "item_rice", "canonical_name": "rice", "new_quantity_value": "1/2", "quantity_type": "capacity_bucket" }
  ],
  "requires_confirmation": false }
```

Created only by the ad-hoc update flow or `confirm-cooked` — never by recipe recommendation (invariant 7).

### 4.11 PreferenceRule (`models/preference_rule.py`)

Generalized, structured — never hardcoded strings:

```json
{
  "preference_id": "pref_001",
  "target_scope": "product | brand | category | ingredient | cuisine | store | package_size",
  "target_value": "Fage",
  "applies_to": { "canonical_item": "Greek yogurt", "subcategory": "plain yogurt" },
  "sentiment": "positive | negative | neutral",
  "reason": "too sour",
  "strength": "weak | medium | strong",
  "future_action": "avoid | prefer | remind | suggest_alternative | ask_before_buying",
  "created_from": "user_review_after_first_use",
  "created_at": "timestamp",
  "active": true
}
```

Rules: strong preferences only after first use (before first use → `preference_hint`); brand dislike never generalizes to a whole category unless the user says so.

### 4.12 BackgroundJob (`models/background_job.py`)

```json
{
  "job_id": "job_001",
  "job_type": "grocery_image_check_in",
  "status": "queued | processing | completed | failed | needs_review",
  "user_id": "user_001",
  "image_ids": ["img_001", "img_002"],
  "created_at": "timestamp",
  "completed_at": null,
  "error": null,
  "steps": [
    { "step": "image_storage",      "status": "completed" },
    { "step": "segmentation",       "status": "queued" },
    { "step": "object_detection",   "status": "queued" },
    { "step": "ocr",                "status": "queued" },
    { "step": "product_enrichment", "status": "queued" }
  ]
}
```

Written in the same transaction as the check-in request. The job row — not Celery — is the durable source of truth for status.

---

## 5. Evidence hierarchy (governs every write)

| Evidence Source | Meaning | Trust Level |
| --------------- | ------- | ----------- |
| User manual confirmation | User explicitly confirmed a value | Highest |
| User edit | User corrected a system estimate | Highest |
| Checklist cross-off | Planned item was bought | Very high |
| Barcode match | Exact product candidate | High |
| Receipt OCR | Product/price/quantity evidence | Medium-high |
| Label OCR | Brand/product/size estimate | Medium |
| Product image detection | Category/count estimate | Medium |
| Segmentation result | Product region evidence | Medium |
| Silent image check-in | Background estimate | Medium/low until reviewed |
| API enrichment | External metadata | Depends on match confidence |
| Web search enrichment | External metadata | Must be source- and confidence-labeled |
| LLM inference | Planning/explanation only | **Not a source of truth** |

The LLM can propose updates; only structured tools validate and commit them (see `architecture.md` §7–§9).
