# PantryOps Edge — API Specification

REST contract from `Manifest.md` §19, organized by router. All routes live under `backend/app/routes/`, validate with Pydantic schemas from `backend/app/schemas/`, and depend on `get_db` + `get_current_user`. Error responses follow one shape: `{"detail": "<field or resource>: <what is wrong and how to fix it>"}`.

Conventions:

- IDs are UUIDs; timestamps are ISO-8601 UTC.
- Any endpoint that writes pantry state does so through `services/ledger.py::apply_update()` — no exceptions.
- 404 for missing resources, 409 for conflicts (e.g., double cross-off), 422 for validation failures.

---

## Shopping (`routes/shopping.py`)

### POST /shopping-lists — create a shopping list

```json
{
  "goal": "weekly groceries",
  "cuisine_preferences": ["Indian", "Mexican"],
  "dietary_restrictions": ["no beef"],
  "protein_goal": "high",
  "budget": 60
}
```

Returns 201 with a categorized list; every item has `canonical_name`, `category`, `desired_quantity`, `priority`, and a human-readable `reason`. The planner never includes restricted items and never ignores strong negative preference rules.

### POST /shopping-lists/{list_id}/items/{item_id}/confirm — cross off an item

```json
{ "status": "bought" }
```

Creates a `ShoppingConfirmationEvent` (`confirmation_source: checklist_cross_off`, confidence 1.0) and inserts a pantry item via the ledger with `canonical_name` user-confirmed and brand/size/price `unknown`. Returns 200 with the event and the new `pantry_item_id`. 409 if already confirmed.

## Assist (`routes/assist.py`)

### POST /shopping/assist — while-shopping question

```json
{
  "question": "Should I buy this yogurt?",
  "image_id": "img_123",
  "shopping_session_id": "session_001"
}
```

Answers from preferences + shopping list + pantry ledger + optional image. Response includes the answer text and any preference rules it applied. Never writes the ledger, never makes medical claims, never claims exact product identity without OCR/barcode evidence. Output passes the Auditor before returning.

## Images and check-in (`routes/images.py`, `routes/checkin.py`)

### POST /images — upload an image (active or check-in)

Authenticated multipart upload + metadata (`capture_context`, `shopping_session_id`). Only decoded JPEG and PNG images up to 10 MiB and 4096×4096 are accepted; the server re-encodes uploads to strip metadata. Refused (403) unless the user's unexpired consent state allows storage. Returns 201 with `image_id` and the recorded `consent_status` / `retention_policy`.

### POST /check-in/groceries — post-shopping silent check-in

```json
{
  "shopping_session_id": "session_001",
  "image_ids": ["img_001", "img_002"],
  "processing_mode": "silent_background_enrichment"
}
```

Creates the durable `BackgroundJob` row in the request transaction, then publishes the Celery chain after commit. A periodic relay recovers committed jobs if publication fails. Returns 202 with `job_id` and initial step statuses. 403 without valid session consent; 422 with zero images (silent mode never runs without user-provided photos).

### GET /jobs/{job_id} — job status

Returns the authenticated user's `BackgroundJob` row: overall status plus per-step status, for the mobile status screen (polled with capped backoff; rendered in an `aria-live` region).

## Vision (`routes/vision.py`)

### POST /vision/analyze — on-demand analysis

```json
{
  "image_id": "img_001",
  "image_type": "product_label | receipt | pantry | grocery_check_in"
}
```

Runs the appropriate vision path and returns detections / OCR fields / barcode value as **estimates with confidence** — this endpoint never writes the ledger directly.

## Pantry (`routes/pantry.py`)

### GET /pantry/items — list items (filter by lifecycle status, low stock)

### GET /pantry/items/{item_id} — item detail with full SourcedField metadata

### POST /pantry/items/{item_id}/quantity — update quantity

```json
{
  "quantity_type": "capacity_bucket",
  "quantity_value": "1/2",
  "source": "user_manual_update"
}
```

Validated against the item's quantity type (422 on a bucket value for a count item). Applied via the ledger; sets status `user_confirmed`.

### POST /pantry/items/{item_id}/fields/{field_name} — confirm / edit / reject a field

```json
{ "action": "edit", "value": "Chobani" }
```

`confirm` sets `user_confirmed`; `edit` sets `user_edited` with the new value; `reject` sets `rejected`. All through `apply_update()`.

## Recipes (`routes/recipes.py`)

### POST /recipes/recommend

```json
{
  "meal_type": "dinner",
  "time_limit_minutes": 30,
  "cuisine_preference": "Indian"
}
```

Returns recipes with `available_ingredients`, `missing_ingredients`, and expected inventory impact. Respects restrictions and disliked brands; prefers use-soon items. **Never deducts inventory.** Auditor verifies every cited ingredient exists in the ledger.

### POST /recipes/{recipe_id}/confirm-cooked

```json
{
  "used_items": [
    { "pantry_item_id": "item_egg", "amount_used": 2 }
  ]
}
```

The only path that deducts inventory from cooking: writes a `ConsumptionEvent` and applies quantity changes via the ledger. Sets `low_quantity` / `reorder_candidate` lifecycle flags when thresholds hit.

## Reviews (`routes/reviews.py`)

### POST /reviews

```json
{
  "pantry_item_id": "item_001",
  "review": "too sour",
  "after_first_use": true
}
```

With `after_first_use: true` → creates a structured `PreferenceRule` at the correct scope. With `false` → stored as `preference_hint` only. Never generalizes brand → category unless the user's text says so.

## Consumption (`routes/consumption.py`)

### POST /consumption/ad-hoc — vague or explicit usage update

```json
{ "message": "I used a lot of milk" }
```

Vague input returns a clarification with the correct scale for the item (`full/3/4/1/2/1/4/empty` for liquids and bulk; a count question for solids). Explicit input (`{"pantry_item_id": "...", "new_quantity_value": "1/2"}`) applies via the ledger.

## Health (`routes/health.py`)

### GET /healthz — liveness: `{"status": "ok", "service": "pantryops"}`
### GET /readyz — readiness: 503 until DB and Redis reachable.
