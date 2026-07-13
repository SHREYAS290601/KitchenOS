# PantryOps Edge — Project Manifest

## 0. Project Identity

### Project Name

**PantryOps Edge**

### One-Line Description

**PantryOps Edge is a mobile-first, checklist-confirmed, edge-vision grocery memory app that helps users plan groceries, confirm purchases, enrich product details from images/OCR/barcodes, track pantry quantities, recommend recipes, and improve future shopping lists from usage and reviews.**

### Short Product Pitch

PantryOps Edge helps a user answer:

```text
What should I buy?
What did I actually buy?
What do I currently have?
What can I cook?
What is running low?
What did I dislike last time?
What should go on my next shopping list?
```

### Core Identity

PantryOps Edge is not just:

* a recipe app;
* a grocery checklist;
* a receipt parser;
* a fridge scanner;
* a calorie tracker;
* a barcode scanner;
* a food database wrapper;
* a generic LLM assistant.

It is:

> **A mobile grocery operating system powered by checklist confirmation, edge vision, editable estimates, structured pantry memory, and LLM planning.**

---

## 1. Core Thesis

Most grocery apps fail because they do not know what the user actually bought, owns, used, disliked, or needs next.

PantryOps Edge solves this by combining:

```text
active grocery planning
+ active while-shopping assistance
+ checklist-based purchase confirmation
+ optional post-shopping silent image enrichment
+ edge object detection and segmentation
+ OCR / barcode / receipt enrichment
+ editable estimated fields
+ fail-safe quantity scales
+ structured pantry ledger
+ LLM-based recipe and shopping planning
+ product review memory after first use
```

The key rule:

> **User confirmation creates truth. Checklist confirms purchase. Vision and OCR create editable estimates. APIs enrich those estimates. The ledger stores sourced states. The LLM plans and explains from the ledger.**

---

## 2. Problem Statement

A student or individual who cooks for themselves often faces these problems:

1. They do not always know what groceries to buy.
2. They forget what they already have at home.
3. They buy duplicates.
4. They waste produce because they forget to use it.
5. They do not know what recipes they can make with current groceries.
6. They may not scan receipts every time.
7. They may want help while shopping.
8. They may want the system to remember disliked brands/products.
9. They may use vague language like “I used a lot of milk.”
10. They want a practical system, not a perfect but unrealistic AI inventory tool.

PantryOps Edge is designed around the way people actually shop:

```text
Plan before shopping.
Ask questions during shopping.
Cross off bought items.
Upload grocery photos after shopping if desired.
Let the app enrich product details in the background.
Use the pantry ledger for recipes and next-list planning.
```

---

## 3. Target Users

### Primary Users

* Students who cook for themselves.
* Busy professionals.
* People living alone.
* Budget-conscious grocery shoppers.
* People who meal prep.
* People with dietary restrictions.
* People tracking protein/carb-heavy meals.
* People who want fewer duplicate purchases.
* People who want to reduce food waste.
* People who want simple pantry memory without typing everything manually.

### Secondary Commercial Users

* Grocery-tech apps.
* Meal-planning apps.
* Smart kitchen apps.
* Personal finance/food-budget apps.
* Student lifestyle apps.
* Retail companion apps.
* Nutrition-lite consumer apps.

---

## 4. Product Scope

### In Scope

PantryOps Edge should support:

1. mobile-first grocery planning;
2. shopping checklist generation;
3. manual cross-off confirmation;
4. active while-shopping questions;
5. active ad-hoc queries;
6. active recipe recommendation;
7. post-shopping grocery image check-in;
8. silent background product enrichment after grocery check-in;
9. object detection for grocery categories;
10. segmentation for product isolation;
11. OCR for labels, receipts, package text, and expiry labels;
12. barcode/product lookup when available;
13. editable key-value estimates;
14. structured pantry ledger;
15. fail-safe quantity tracking;
16. product review memory after first use;
17. recipe-based inventory deduction after user confirmation;
18. next-list generation from low quantity, frequent items, goals, and preferences;
19. expense summary where price data exists;
20. mobile local cache plus hosted backend.

### Out of Scope for MVP

Do not build these first:

* grocery delivery ordering;
* live Walmart/Target/local store price optimization;
* fully automatic exact grocery recognition;
* exact expiry prediction;
* exact liquid volume measurement;
* medical nutrition advice;
* full calorie/macro medical-grade diet planning;
* multi-user household management;
* smart fridge integration;
* automatic background monitoring without user-uploaded photos;
* active learning from user photos;
* claims that a product is safe/unsafe to consume.

---

## 5. Processing Modes

PantryOps Edge has two major processing modes.

```text
Active Mode:
The user asks, scans, uploads, crosses off, or requests help right now.

Silent Mode:
The user has already bought groceries and intentionally uploads post-shopping grocery photos for background check-in and enrichment.
```

---

## 6. Active Mode

Active mode is user-facing and happens before, during, or after shopping when the user asks for help.

### 6.1 Pre-Shopping Active Planning

Example user request:

```text
What should I buy this week? I want high protein meals, mostly Indian food, and no beef.
```

System should consider:

* current pantry ledger;
* low-stock items;
* frequent purchases;
* dietary restrictions;
* cuisine preferences;
* protein/carb goals;
* budget preference;
* disliked products/brands;
* upcoming events;
* items likely to expire soon.

Output:

```text
Suggested shopping list:

Protein:
- eggs
- Greek yogurt
- chicken breast or tofu

Vegetables:
- spinach
- tomatoes
- onions

Carbs:
- rice
- pasta

Frequent restocks:
- milk
- bananas
```

---

### 6.2 During-Shopping Active Assistance

The user can ask questions while shopping.

Examples:

```text
Should I buy this yogurt?
Is this enough for 3 meals?
Can I replace paneer with tofu?
Which one is better for high protein?
Does this fit my restrictions?
I am confused between these two products.
```

The system can use:

* user preferences;
* shopping list;
* pantry ledger;
* image uploaded by user;
* label OCR;
* barcode;
* nutrition/product APIs;
* LLM reasoning.

Example answer:

```text
This looks like plain Greek yogurt. You previously disliked sour plain yogurt from this brand, so I would avoid this one unless you want to retry it. A vanilla Greek yogurt or another brand may fit your preference better.
```

---

### 6.3 Checklist Active Confirmation

The user crosses off bought items.

Example:

```text
✓ milk
✓ tomatoes
✓ onions
✓ chicken
✗ Greek yogurt
```

Cross-off confirms:

```text
This planned item was bought.
```

It does not confirm:

* exact brand;
* exact price;
* exact product type;
* package size;
* nutrition details;
* expiry date.

Those details require OCR, barcode, receipt, image, API enrichment, or user edits.

---

### 6.4 Active Ad-Hoc Inventory Updates

The user may say:

```text
I used a lot of milk.
```

The system should not guess exact remaining quantity.

It should ask:

```text
How much milk is left?

[Full] [3/4] [1/2] [1/4] [Empty]
```

For solids:

```text
How many tomatoes are left?
```

For bulk solids:

```text
How much rice is left?

[Full] [3/4] [1/2] [1/4] [Empty]
```

---

### 6.5 Active Recipe Requests

The user may ask:

```text
What can I cook tonight?
```

System should:

* read pantry ledger;
* prefer items already available;
* prefer use-soon items;
* respect restrictions;
* avoid disliked products/brands where relevant;
* show missing ingredients;
* not deduct inventory until user confirms cooking.

---

### 6.6 Active Photos Should Be Stored as Evidence

If the user uploads a photo during an active query, the photo should be stored if the user has consented to grocery image memory.

Example:

```text
User while shopping:
Should I buy this milk?
```

The user uploads a product photo.

The system answers immediately.

Then the same photo may later be reused for background enrichment if the user buys/crosses off that item.

### Active Photo Record

```json
{
  "image_id": "img_123",
  "capture_context": "while_shopping_query",
  "user_intent": "product_decision_help",
  "related_item_candidate": "milk",
  "linked_shopping_session_id": "session_001",
  "stored_for_future_enrichment": true,
  "processing_mode": "active_then_background_enrichment",
  "user_consent_status": "granted_for_session"
}
```

---

## 7. Silent Mode

Silent mode only happens **after shopping**.

It is not always-on monitoring.

It is not active learning.

It does not run on photos the user did not intentionally upload.

### Trigger

The user intentionally chooses a grocery check-in action:

```text
I bought groceries. Here are pictures of what I bought.
```

or taps:

```text
Check in groceries with photos
```

### Silent Flow Responsibilities

Silent processing should:

1. store uploaded grocery images;
2. create background enrichment job;
3. segment individual products;
4. detect item categories;
5. crop labels/product regions;
6. run OCR on labels and packages;
7. detect barcodes when visible;
8. estimate quantities;
9. use APIs or web sources for product/nutrition details;
10. create or update pantry records as editable estimates;
11. flag low-confidence records for review;
12. avoid interrupting user unless review is needed.

### Silent Check-In Pipeline

```text
User uploads post-shopping grocery photos
        ↓
Images stored with consent
        ↓
Background job created
        ↓
Segmentation Agent separates product regions
        ↓
Object Detection Agent identifies grocery categories
        ↓
OCR Agent extracts label/package text
        ↓
Barcode Agent checks visible barcodes
        ↓
Product Enrichment Agent queries APIs/sources
        ↓
Candidate pantry records created or updated
        ↓
Field-level values stored as estimates
        ↓
Auditor flags conflicts or low-confidence fields
        ↓
Review screen shows only useful confirmations
```

### Example Silent Check-In Output

```text
Estimated grocery check-in complete.

Detected:
- Milk carton — likely whole milk — confidence 0.82
- Tomatoes — count estimate: 4 — confidence 0.77
- Rice bag — quantity estimate: full — confidence 0.68
- Yogurt tub — brand unreadable — needs review

4 items added as estimates.
1 item needs confirmation.
```

---

## 8. Consent and Privacy Rules

Photos should only be stored when the user has opted into image-based grocery memory.

The app should provide clear choices:

```text
Save uploaded grocery images to improve pantry tracking?

[Yes, save for this shopping session]
[Always save grocery images]
[Do not save after answering]
```

Silent enrichment must never run on photos the user did not intentionally provide.

### Required Consent States

```text
not_requested
denied
granted_for_single_image
granted_for_session
always_granted
revoked
```

### Photo Retention Options

The user should be able to choose:

```text
delete after answer
delete after enrichment
keep for pantry memory
keep until manually deleted
```

---

## 9. Evidence Hierarchy

PantryOps Edge must rank evidence sources clearly.

| Evidence Source          | Meaning                           | Trust Level                                   |
| ------------------------ | --------------------------------- | --------------------------------------------- |
| User manual confirmation | User explicitly confirmed a value | Highest                                       |
| User edit                | User corrected system estimate    | Highest                                       |
| Checklist cross-off      | Planned item was bought           | Very high                                     |
| Barcode match            | Exact product candidate           | High                                          |
| Receipt OCR              | Product/price/quantity evidence   | Medium-high                                   |
| Label OCR                | Brand/product/size estimate       | Medium                                        |
| Product image detection  | Category/count estimate           | Medium                                        |
| Segmentation result      | Product region evidence           | Medium                                        |
| Silent image check-in    | Background estimate               | Medium/low until reviewed                     |
| API enrichment           | External metadata                 | Depends on match confidence                   |
| Web search enrichment    | External metadata                 | Must be source-labeled and confidence-labeled |
| LLM inference            | Planning/explanation only         | Not source of truth                           |

### Evidence Rule

The LLM can propose updates, but structured tools must validate and commit updates to the pantry ledger.

---

## 10. Editable Estimate System

Every value produced by OCR, object detection, segmentation, barcode matching, API lookup, or web enrichment must be treated as an estimate unless user-confirmed.

### Field-Level Metadata

Every populated key-value pair should include:

```json
{
  "field_name": "brand",
  "field_value": "Chobani",
  "source": "label_ocr",
  "confidence": 0.84,
  "status": "estimated",
  "editable": true,
  "last_updated": "timestamp"
}
```

### Field Status Values

```text
estimated
user_confirmed
user_edited
rejected
unknown
conflicting
```

### User Actions

For each estimated field, the user should be able to:

```text
confirm
edit
reject
leave_as_estimate
```

### Example Mobile UI

```text
Estimated details:

Brand: Chobani
Source: Label OCR
Confidence: 84%

Product: Greek Yogurt
Source: Label OCR
Confidence: 76%

Size: 32 oz
Source: OCR
Confidence: 61%

[Confirm All] [Edit] [Leave as Estimate]
```

---

## 11. Quantity System

The quantity system should be simple, fail-safe, and user-correctable.

### 11.1 Quantity Philosophy

Do not pretend to know exact quantities when the real world is ambiguous.

Use coarse, practical scales.

---

### 11.2 Countable Solids

Track countable solids in hard quantities or discrete units.

Examples:

```text
1 big block of cheese
3 tomatoes
9 potatoes
1 watermelon
6 eggs
2 apples
1 loaf of bread
1 pack of chicken
1 bunch of spinach
```

Supported unit labels:

```text
count
piece
block
pack
box
bag
loaf
bunch
container
tray
dozen
```

Example:

```json
{
  "canonical_name": "tomatoes",
  "quantity_type": "count",
  "quantity_value": 3,
  "unit_label": "tomatoes",
  "status": "user_confirmed"
}
```

---

### 11.3 Liquids

Liquids use capacity buckets.

Allowed values:

```text
full
3/4
1/2
1/4
empty
unknown
```

Examples:

```text
milk: full
juice: 1/2
oil: 3/4
soy sauce: 1/4
```

Example:

```json
{
  "canonical_name": "milk",
  "quantity_type": "capacity_bucket",
  "quantity_value": "1/2",
  "unit_label": "carton",
  "status": "user_confirmed"
}
```

---

### 11.4 Bulk Solids

Bulk solids also use capacity buckets.

Examples:

```text
rice bag
flour bag
sugar bag
lentils
pasta box
cereal box
oats container
```

Allowed values:

```text
full
3/4
1/2
1/4
empty
unknown
```

Example:

```json
{
  "canonical_name": "rice",
  "quantity_type": "capacity_bucket",
  "quantity_value": "3/4",
  "unit_label": "bag",
  "status": "estimated"
}
```

---

### 11.5 Packaged Units

Packaged units can be count-based.

Examples:

```text
4 yogurt cups
6 protein bars
12 eggs
2 pasta boxes
3 ramen packs
```

Example:

```json
{
  "canonical_name": "protein bars",
  "quantity_type": "count",
  "quantity_value": 6,
  "unit_label": "bars"
}
```

---

### 11.6 Unknown Quantity

If uncertain, store unknown and ask later.

```json
{
  "canonical_name": "spinach",
  "quantity_type": "unknown",
  "quantity_value": null,
  "needs_user_confirmation": true
}
```

---

## 12. Item Lifecycle

Each grocery item can move through these states:

```text
planned
bought
estimated
enriched
stored
opened
partially_used
low_quantity
used_up
expired_or_discarded
review_eligible
reviewed
reorder_candidate
archived
```

Example lifecycle:

```text
milk
  → planned
  → bought via checklist
  → enriched via label OCR
  → stored as full
  → opened
  → updated to 1/2
  → used_up
  → reorder_candidate
  → added to next shopping list
```

---

## 13. Preference and Review System

Preference rules must be generalized.

Do not store hardcoded strings like:

```text
avoid_brand_for_plain_yogurt
```

Instead, use a structured preference-rule schema.

### Preference Rule Schema

```json
{
  "preference_id": "pref_001",
  "target_scope": "product | brand | category | ingredient | cuisine | store | package_size",
  "target_value": "Fage",
  "applies_to": {
    "canonical_item": "Greek yogurt",
    "subcategory": "plain yogurt",
    "brand": "Fage"
  },
  "sentiment": "positive | negative | neutral",
  "reason": "too sour",
  "strength": "weak | medium | strong",
  "future_action": "avoid | prefer | remind | suggest_alternative | ask_before_buying",
  "created_from": "user_review_after_first_use",
  "created_at": "timestamp",
  "active": true
}
```

### Example

User says after first use:

```text
This yogurt was too sour. Don’t recommend this brand again.
```

Stored rule:

```json
{
  "target_scope": "brand",
  "target_value": "Fage",
  "applies_to": {
    "canonical_item": "Greek yogurt",
    "subcategory": "plain yogurt"
  },
  "sentiment": "negative",
  "reason": "too sour",
  "strength": "strong",
  "future_action": "avoid",
  "created_from": "user_review_after_first_use",
  "active": true
}
```

### Review Rule

Reviews should only become strong preference memory after first use.

If the user says something before first use, store it as:

```text
preference_hint
```

not:

```text
product_review
```

---

## 14. Main Data Models

## 14.1 Pantry Item

```json
{
  "pantry_item_id": "item_001",
  "user_id": "user_001",
  "canonical_name": {
    "value": "milk",
    "source": "checklist",
    "confidence": 1.0,
    "status": "user_confirmed",
    "editable": true
  },
  "display_name": {
    "value": "Organic Whole Milk",
    "source": "label_ocr",
    "confidence": 0.82,
    "status": "estimated",
    "editable": true
  },
  "category": {
    "value": "dairy",
    "source": "product_enrichment",
    "confidence": 0.91,
    "status": "estimated",
    "editable": true
  },
  "brand": {
    "value": null,
    "source": null,
    "confidence": null,
    "status": "unknown",
    "editable": true
  },
  "product_name": {
    "value": null,
    "source": null,
    "confidence": null,
    "status": "unknown",
    "editable": true
  },
  "quantity_type": "capacity_bucket",
  "quantity_value": {
    "value": "full",
    "source": "checklist_default",
    "confidence": 0.7,
    "status": "estimated",
    "editable": true
  },
  "unit_label": "carton",
  "purchase_date": "2026-06-28",
  "storage_location": "fridge",
  "estimated_use_by": null,
  "status": "stored",
  "source_event_id": "event_001",
  "needs_user_review": false,
  "created_at": "timestamp",
  "updated_at": "timestamp"
}
```

---

## 14.2 Shopping List Item

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

---

## 14.3 Shopping Confirmation Event

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

---

## 14.4 Image Evidence Record

```json
{
  "image_id": "img_001",
  "user_id": "user_001",
  "capture_context": "post_shopping_check_in",
  "processing_mode": "silent_background_enrichment",
  "linked_shopping_session_id": "session_001",
  "related_item_candidate": null,
  "storage_uri": "s3://bucket/img_001.jpg",
  "consent_status": "granted_for_session",
  "retention_policy": "delete_after_enrichment",
  "created_at": "timestamp"
}
```

---

## 14.5 Vision Detection

```json
{
  "detection_id": "det_001",
  "image_id": "img_001",
  "label": "tomato",
  "bbox": [120, 80, 210, 190],
  "confidence": 0.86,
  "model_name": "grocery_detector_v1",
  "created_at": "timestamp"
}
```

---

## 14.6 Segmentation Result

```json
{
  "segmentation_id": "seg_001",
  "image_id": "img_001",
  "detection_id": "det_001",
  "mask_uri": "s3://bucket/masks/seg_001.png",
  "crop_uri": "s3://bucket/crops/item_001.png",
  "confidence": 0.81
}
```

---

## 14.7 OCR Result

```json
{
  "ocr_id": "ocr_001",
  "image_id": "img_001",
  "crop_uri": "s3://bucket/crops/item_001.png",
  "raw_text": "CHOBANI GREEK YOGURT 32 OZ",
  "structured_fields": {
    "brand": "Chobani",
    "product_name": "Greek Yogurt",
    "package_size": "32 oz"
  },
  "confidence": 0.84,
  "engine": "paddleocr",
  "created_at": "timestamp"
}
```

---

## 14.8 Product Enrichment Record

```json
{
  "enrichment_id": "enrich_001",
  "pantry_item_id": "item_001",
  "barcode": null,
  "brand": {
    "value": "Chobani",
    "source": "label_ocr",
    "confidence": 0.84,
    "status": "estimated"
  },
  "product_name": {
    "value": "Greek Yogurt",
    "source": "label_ocr",
    "confidence": 0.78,
    "status": "estimated"
  },
  "nutrition_source": "open_food_facts_or_usda",
  "dietary_info_source": "api_enrichment",
  "created_at": "timestamp"
}
```

---

## 14.9 Consumption Event

```json
{
  "consumption_id": "consume_001",
  "timestamp": "timestamp",
  "source": "user_message",
  "items_used": [
    {
      "pantry_item_id": "item_egg",
      "canonical_name": "eggs",
      "amount_used": 2,
      "unit_label": "eggs"
    },
    {
      "pantry_item_id": "item_rice",
      "canonical_name": "rice",
      "new_quantity_value": "1/2",
      "quantity_type": "capacity_bucket"
    }
  ],
  "requires_confirmation": false
}
```

---

## 14.10 Preference Rule

```json
{
  "preference_id": "pref_001",
  "target_scope": "brand",
  "target_value": "Fage",
  "applies_to": {
    "canonical_item": "Greek yogurt",
    "subcategory": "plain yogurt"
  },
  "sentiment": "negative",
  "reason": "too sour",
  "strength": "strong",
  "future_action": "avoid",
  "created_from": "user_review_after_first_use",
  "active": true,
  "created_at": "timestamp"
}
```

---

## 14.11 Background Job

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
    {
      "step": "image_storage",
      "status": "completed"
    },
    {
      "step": "segmentation",
      "status": "queued"
    },
    {
      "step": "object_detection",
      "status": "queued"
    },
    {
      "step": "ocr",
      "status": "queued"
    },
    {
      "step": "product_enrichment",
      "status": "queued"
    }
  ]
}
```

---

## 15. Agent Manifest

## 15.1 Input Router Agent

### Purpose

Routes user inputs to the correct agents.

### Inputs

* user text;
* image upload;
* receipt upload;
* label photo;
* barcode scan;
* checklist action;
* recipe request;
* ad-hoc update.

### Outputs

* normalized intent;
* selected agents;
* structured payload.

### Forbidden Actions

* must not edit the ledger directly;
* must not infer purchases;
* must not generate recipe directly.

---

## 15.2 Shopping Planner Agent

### Purpose

Creates shopping lists from pantry state, goals, restrictions, preferences, and upcoming context.

### Inputs

* pantry ledger;
* user goals;
* cuisine preferences;
* protein/carb preference;
* meat restrictions;
* budget preference;
* product reviews;
* frequent items;
* upcoming events.

### Outputs

* categorized shopping list;
* priority;
* reason per item;
* alternatives.

### Forbidden Actions

* must not mark items as bought;
* must not recommend restricted items;
* must not ignore strong negative preference rules.

---

## 15.3 Checklist Confirmation Agent

### Purpose

Confirms bought/not-bought status through user cross-off.

### Inputs

* shopping list item;
* user action;
* shopping session.

### Outputs

* purchase confirmation event;
* pantry insertion request.

### Forbidden Actions

* must not infer exact brand;
* must not infer exact price;
* must not infer product size.

---

## 15.4 While-Shopping Assistant Agent

### Purpose

Handles active shopping questions.

### Inputs

* user question;
* optional image;
* optional OCR/barcode;
* current shopping list;
* pantry ledger;
* preferences.

### Outputs

* buying advice;
* product comparison;
* restriction-aware guidance;
* optional photo storage/enrichment event.

### Forbidden Actions

* must not make medical claims;
* must not claim exact product identity without evidence;
* must not update ledger unless user confirms purchase.

---

## 15.5 Mobile Check-In Agent

### Purpose

Handles post-shopping grocery photo upload and starts silent background enrichment.

### Inputs

* uploaded grocery images;
* shopping session;
* optional checklist context.

### Outputs

* image records;
* background job ID;
* processing status.

### Forbidden Actions

* must not claim final identity immediately;
* must not auto-confirm low-confidence values;
* must not run without user-provided images.

---

## 15.6 Background Enrichment Agent

### Purpose

Runs silent product understanding after post-shopping check-in.

### Responsibilities

* call segmentation;
* call object detection;
* call OCR;
* call barcode detection;
* call product enrichment;
* create estimated records;
* flag uncertain values.

### Forbidden Actions

* must not overwrite user-confirmed values;
* must not mark estimated fields as confirmed;
* must not call the process active learning.

---

## 15.7 Edge Vision Agent

### Purpose

Detects grocery objects/categories and estimates counts where possible.

### Inputs

* product/pantry/grocery image;
* optional expected item list.

### Outputs

* labels;
* bounding boxes;
* confidence scores;
* count estimates.

### Forbidden Actions

* must not identify exact brand without OCR/barcode;
* must not update ledger directly.

---

## 15.8 Segmentation Agent

### Purpose

Segments individual products and creates crops for OCR or detailed inspection.

### Inputs

* image;
* bounding boxes;
* user-selected region.

### Outputs

* masks;
* cropped item images;
* region metadata.

### Forbidden Actions

* must not classify final item alone;
* must not write to pantry ledger.

---

## 15.9 OCR / Label Agent

### Purpose

Extracts text from labels, receipts, packaging, expiry labels, and nutrition panels.

### Inputs

* product crop;
* receipt image;
* label image.

### Outputs

* raw text;
* structured key-value candidates;
* confidence.

### Forbidden Actions

* must not silently correct uncertain OCR;
* must not mark fields as confirmed.

---

## 15.10 Barcode Agent

### Purpose

Reads barcode when visible and queries product sources.

### Inputs

* barcode crop;
* image;
* barcode number.

### Outputs

* barcode value;
* product lookup candidate;
* confidence.

### Forbidden Actions

* must not invent barcode;
* must not match product without reliable barcode value.

---

## 15.11 Product Enrichment Agent

### Purpose

Uses OCR/barcode/product APIs/web sources to enrich product details.

### Inputs

* canonical item;
* OCR fields;
* barcode result;
* image category;
* product API results;
* web-search result if enabled.

### Outputs

* brand;
* product name;
* package size;
* dietary info;
* nutrition fields;
* source-labeled metadata.

### Forbidden Actions

* must not invent product matches;
* must not create health claims;
* must source every enriched field.

---

## 15.12 Pantry Ledger Agent

### Purpose

Maintains the canonical inventory and applies updates based on source hierarchy.

### Inputs

* checklist confirmations;
* user edits;
* OCR estimates;
* vision estimates;
* enrichment results;
* consumption updates;
* recipe confirmations.

### Outputs

* updated pantry item;
* change log;
* source metadata;
* confidence status.

### Rules

* user confirmation beats model inference;
* user edit beats all estimates;
* barcode beats OCR when reliable;
* OCR beats general object detection for exact product fields;
* object detection supports category/count estimates;
* LLM cannot directly mutate inventory.

---

## 15.13 Recipe Planner Agent

### Purpose

Recommends meals from available inventory and user preferences.

### Inputs

* pantry ledger;
* cuisine goals;
* dietary restrictions;
* protein/carb preference;
* use-soon items;
* disliked products/brands.

### Outputs

* recipe suggestions;
* available ingredients;
* missing ingredients;
* expected inventory impact.

### Forbidden Actions

* must not deduct inventory until user confirms;
* must not recommend restricted foods;
* must not claim unavailable ingredients are available.

---

## 15.14 Consumption Update Agent

### Purpose

Updates quantities after use.

### Inputs

* user message;
* recipe confirmation;
* quantity state;
* pantry item.

### Outputs

* quantity update;
* low-stock flag;
* reorder trigger.

### Rule for Vague Usage

If user says:

```text
used a lot of xyz
```

ask how much remains using the correct scale.

---

## 15.15 Preference Review Agent

### Purpose

Stores product/brand/category preferences after first use.

### Inputs

* user review;
* product record;
* first-use status.

### Outputs

* generalized preference rule;
* future recommendation adjustment.

### Forbidden Actions

* must not overgeneralize from brand to entire category unless user says so;
* must not store strong review before first use.

---

## 15.16 Store / Cost Agent

### Purpose

Creates estimated expense reports and optional store grouping.

### Inputs

* shopping list;
* user store preference;
* receipt price data;
* manual price entries;
* product API price if available.

### Outputs

* estimated expense report;
* known prices;
* unknown prices;
* store grouping.

### Forbidden Actions

* must not claim live prices or availability without verified source.

---

## 15.17 Estimate Review Agent

### Purpose

Shows uncertain estimated values to the user for confirmation/editing.

### Inputs

* estimated fields;
* low-confidence records;
* conflicts;
* missing values.

### Outputs

* review prompt;
* user confirmation/edit/rejection.

---

## 15.18 Source Attribution Agent

### Purpose

Ensures every field has value, source, confidence, status, and editability.

### Inputs

* all candidate fields from agents.

### Outputs

* source-tracked record.

### Forbidden Actions

* must not merge values without retaining provenance.

---

## 15.19 Auditor Agent

### Purpose

Checks final outputs and ledger updates for unsupported claims or unsafe assumptions.

### Audits

* dietary restriction violations;
* recipe using unavailable items;
* unsupported product claims;
* low-confidence estimates displayed as facts;
* inventory updates without source;
* preference overgeneralization;
* silent mode without consent.

---

## 16. Mobile-First Architecture

### Frontend

The UI should be mobile-only.

Use:

```text
React Native
Expo or bare React Native
mobile camera
barcode scanning
image upload
offline checklist cache
push notifications
```

### Why Mobile-Only

* phone cameras are better;
* barcode scanning is natural on mobile;
* grocery shopping happens away from desktop;
* pantry/fridge image capture is mobile-native;
* user can ask active questions while shopping;
* push notifications support low-stock/use-soon reminders.

---

## 17. Backend and Storage Architecture

PantryOps Edge should be an app with:

```text
React Native mobile frontend
+ hosted backend
+ database
+ image storage
+ background jobs
+ agent orchestration
```

### Recommended Architecture

```text
React Native App
  ├── camera capture
  ├── barcode scanning
  ├── local shopping checklist cache
  ├── pantry snapshot cache
  ├── user edits
  └── active chat/query interface

Hosted Backend
  ├── API layer
  ├── pantry ledger database
  ├── image storage
  ├── background enrichment queue
  ├── OCR/detection/segmentation services
  ├── product enrichment services
  ├── LLM agent orchestration
  └── audit/logging layer
```

### Storage Strategy

Recommended:

```text
Hybrid storage:
- Mobile local cache for shopping checklist and pantry snapshot.
- Hosted backend as source of truth.
- Cloud image/object storage for uploaded grocery images.
- Background job queue for silent enrichment.
```

### MVP Database

Use:

```text
PostgreSQL hosted
or SQLite for local-only prototype
```

For production-like app:

```text
PostgreSQL + object storage + job queue
```

---

## 18. External Data Sources

### 18.1 Open Food Facts

Use for:

* barcode lookup;
* brand;
* product name;
* ingredients;
* nutrition facts;
* packaging metadata.

### 18.2 USDA FoodData Central

Use for:

* generic food nutrition;
* ingredient-level nutrition;
* food category enrichment.

### 18.3 CORD Receipt Dataset

Use for:

* receipt OCR/parsing experiments;
* receipt field extraction benchmarks.

### 18.4 Grocery Store Dataset

Use for:

* grocery item image recognition;
* produce/carton classification;
* object detection/classification baseline.

### 18.5 User-Owned Data

Eventually, the most important data is the user’s own:

* checklists;
* cross-offs;
* pantry photos;
* product photos;
* ad-hoc queries;
* reviews;
* recipe confirmations;
* usage updates.

---

## 19. API Manifest

### 19.1 Create Shopping List

```http
POST /shopping-lists
```

Input:

```json
{
  "goal": "weekly groceries",
  "cuisine_preferences": ["Indian", "Mexican"],
  "dietary_restrictions": ["no beef"],
  "protein_goal": "high",
  "budget": 60
}
```

---

### 19.2 Confirm Shopping Item

```http
POST /shopping-lists/{list_id}/items/{item_id}/confirm
```

Input:

```json
{
  "status": "bought"
}
```

---

### 19.3 Ask While-Shopping Question

```http
POST /shopping/assist
```

Input:

```json
{
  "question": "Should I buy this yogurt?",
  "image_id": "img_123",
  "shopping_session_id": "session_001"
}
```

---

### 19.4 Upload Grocery Check-In Photos

```http
POST /check-in/groceries
```

Input:

```json
{
  "shopping_session_id": "session_001",
  "image_ids": ["img_001", "img_002"],
  "processing_mode": "silent_background_enrichment"
}
```

---

### 19.5 Analyze Image

```http
POST /vision/analyze
```

Input:

```json
{
  "image_id": "img_001",
  "image_type": "product_label | receipt | pantry | grocery_check_in"
}
```

---

### 19.6 Update Pantry Quantity

```http
POST /pantry/items/{item_id}/quantity
```

Input:

```json
{
  "quantity_type": "capacity_bucket",
  "quantity_value": "1/2",
  "source": "user_manual_update"
}
```

---

### 19.7 Recommend Recipes

```http
POST /recipes/recommend
```

Input:

```json
{
  "meal_type": "dinner",
  "time_limit_minutes": 30,
  "cuisine_preference": "Indian"
}
```

---

### 19.8 Confirm Recipe Cooked

```http
POST /recipes/{recipe_id}/confirm-cooked
```

Input:

```json
{
  "used_items": [
    {
      "pantry_item_id": "item_egg",
      "amount_used": 2
    }
  ]
}
```

---

### 19.9 Add Product Review

```http
POST /reviews
```

Input:

```json
{
  "pantry_item_id": "item_001",
  "review": "too sour",
  "after_first_use": true
}
```

---

## 20. MVP Definition

### MVP Name

**PantryOps Edge MVP**

### MVP Must Include

1. React Native mobile app shell.
2. Hosted backend.
3. Pantry ledger with field-level source metadata.
4. Shopping-list generation.
5. Checklist cross-off purchase confirmation.
6. Fail-safe quantity system.
7. Ad-hoc quantity update flow.
8. Active while-shopping question flow.
9. Image upload with consent.
10. Post-shopping grocery check-in.
11. Background enrichment job model.
12. OCR/label extraction baseline.
13. Object detection or grocery classification baseline.
14. Editable estimated fields.
15. Recipe recommendation from ledger.
16. Recipe confirmation and inventory deduction.
17. Product review after first use.
18. Generalized preference rules.
19. Audit layer.

---

## 21. Build Phases

### Phase 0 — Product Definition

Deliverables:

* project manifest;
* README;
* user flows;
* data model;
* agent list;
* active/silent mode spec.

### Phase 1 — Mobile Shell and Backend

Deliverables:

* React Native app shell;
* hosted backend;
* auth placeholder;
* API structure;
* local checklist cache.

### Phase 2 — Pantry Ledger and Quantity System

Deliverables:

* pantry item model;
* field-level metadata;
* quantity model;
* user edit flow;
* ledger update logs.

### Phase 3 — Shopping Checklist

Deliverables:

* create shopping list;
* categorize items;
* cross-off flow;
* purchase confirmation event;
* checklist-to-ledger update.

### Phase 4 — Active Assistance

Deliverables:

* ad-hoc query handling;
* while-shopping assistant;
* active photo upload;
* photo storage consent;
* active-photo background reuse.

### Phase 5 — Silent Grocery Check-In

Deliverables:

* post-shopping image upload;
* background job queue;
* image evidence records;
* silent enrichment workflow.

### Phase 6 — Vision/OCR Enrichment

Deliverables:

* object detection/classification baseline;
* segmentation/cropping;
* OCR extraction;
* barcode support if available;
* editable estimated fields.

### Phase 7 — Product/Nutrition Enrichment

Deliverables:

* Open Food Facts integration;
* USDA integration;
* source-attributed enrichment;
* dietary/product metadata.

### Phase 8 — Recipe and Consumption

Deliverables:

* recipe recommendation;
* missing ingredient detection;
* confirm cooked;
* deduct inventory;
* low-stock triggers.

### Phase 9 — Review and Preference Memory

Deliverables:

* review after first use;
* generalized preference rules;
* avoid/prefer/suggest alternative logic;
* future list adaptation.

### Phase 10 — Evaluation and Demo

Deliverables:

* full demo script;
* test user profile;
* sample shopping session;
* sample grocery images;
* sample ad-hoc queries;
* end-to-end video.

---

## 22. Evaluation Metrics

### Vision Metrics

```text
object detection precision
object detection recall
classification accuracy
count estimate error
segmentation crop usefulness
OCR field extraction accuracy
barcode match success rate
```

### Ledger Metrics

```text
checklist-to-ledger correctness
quantity update correctness
source metadata completeness
estimated-field editability
inventory mutation error rate
```

### Agent Metrics

```text
intent routing accuracy
dietary restriction violation rate
unsupported update rate
recipe availability correctness
preference application correctness
ad-hoc clarification accuracy
```

### User Experience Metrics

```text
time to create shopping list
time to check off groceries
manual corrections required
recipe usefulness rating
low-stock alert usefulness
review preference accuracy
```

---

## 23. Failure Modes and Mitigations

### Object Detection Misclassification

Mitigation:

* store as estimate;
* show confidence;
* ask user to review if important;
* do not auto-confirm exact product.

### OCR Error

Mitigation:

* make extracted fields editable;
* show source and confidence;
* allow rejection.

### Vague Usage

Example:

```text
I used a lot of milk.
```

Mitigation:

* ask remaining quantity using liquid/bulk scale.

### Recipe Uses Missing Item

Mitigation:

* auditor checks recipe ingredients against pantry ledger before output.

### Preference Overgeneralization

Mitigation:

* use structured preference rule with target scope;
* do not generalize brand dislike to whole category unless user says so.

### Silent Processing Without Consent

Mitigation:

* require explicit photo storage/enrichment consent;
* store consent status with every image.

---

## 24. Guardrails

1. Do not claim food is safe or unsafe.
2. Do not claim exact expiry unless date label is read.
3. Do not give medical nutrition advice.
4. Do not override dietary restrictions.
5. Do not auto-deduct inventory from recipe suggestions.
6. Do not treat object detection as exact product identification.
7. Do not treat OCR as perfect.
8. Do not hide estimated status.
9. Do not store inferred values without source/confidence.
10. Do not run silent enrichment on non-consented images.
11. Do not store product reviews as strong rules before first use.
12. Do not overgeneralize preferences.
13. Do not claim live prices without verified source.
14. Do not update user-confirmed fields with lower-confidence estimates.

---

## 25. Recommended Tech Stack

### Mobile Frontend

```text
React Native
Expo
Camera API
Barcode scanner
Push notifications
Local cache
```

### Backend

```text
Python
FastAPI
Pydantic
SQLAlchemy
PostgreSQL
Redis/Celery or equivalent job queue
Object storage for images
```

### Vision

```text
YOLO / RT-DETR / grocery classifier
SAM/SAM2-style segmentation
PaddleOCR / EasyOCR / Tesseract
Barcode scanner library
```

### AI/Agents

```text
LLM with structured JSON output
LangGraph or custom state machine
tool-based ledger mutations
auditor before final response
```

---

## 26. Suggested Repository Structure

```text
pantryops-edge/
├── README.md
├── MANIFEST.md
├── pyproject.toml
├── .env.example
├── mobile/
│   ├── app/
│   ├── screens/
│   ├── components/
│   ├── camera/
│   ├── storage/
│   └── api/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── routes/
│   │   ├── schemas/
│   │   ├── services/
│   │   └── workers/
│   ├── agents/
│   │   ├── input_router.py
│   │   ├── shopping_planner.py
│   │   ├── while_shopping_assistant.py
│   │   ├── checklist_confirmation.py
│   │   ├── mobile_check_in.py
│   │   ├── background_enrichment.py
│   │   ├── edge_vision.py
│   │   ├── segmentation.py
│   │   ├── ocr_label.py
│   │   ├── barcode.py
│   │   ├── product_enrichment.py
│   │   ├── pantry_ledger.py
│   │   ├── recipe_planner.py
│   │   ├── consumption_update.py
│   │   ├── preference_review.py
│   │   ├── estimate_review.py
│   │   ├── source_attribution.py
│   │   └── auditor.py
│   ├── pantry/
│   │   ├── ledger.py
│   │   ├── quantity.py
│   │   ├── lifecycle.py
│   │   └── preferences.py
│   ├── vision/
│   │   ├── detector.py
│   │   ├── segmenter.py
│   │   ├── ocr.py
│   │   ├── barcode.py
│   │   └── preprocessing.py
│   ├── products/
│   │   ├── open_food_facts.py
│   │   ├── usda.py
│   │   └── normalization.py
│   ├── recipes/
│   │   ├── recommender.py
│   │   ├── matcher.py
│   │   └── deduction.py
│   └── evaluation/
│       ├── test_vision.py
│       ├── test_ocr.py
│       ├── test_ledger.py
│       ├── test_agents.py
│       └── metrics.py
├── docs/
│   ├── ARCHITECTURE.md
│   ├── AGENTS.md
│   ├── DATA_MODEL.md
│   ├── QUANTITY_SYSTEM.md
│   ├── ACTIVE_SILENT_FLOWS.md
│   ├── MOBILE_UX.md
│   ├── EVALUATION.md
│   └── ROADMAP.md
└── data/
    ├── samples/
    ├── public/
    ├── user_uploads/
    └── exports/
```

---

## 27. Demo Script

### Step 1 — Pre-Shopping Planning

User:

```text
Make a grocery list for this week. I want high-protein meals, mostly Indian food, no beef.
```

System creates categorized shopping list.

### Step 2 — While Shopping

User uploads yogurt photo:

```text
Should I buy this?
```

System checks preferences and answers.

Photo is stored if consent is granted.

### Step 3 — Checklist Confirmation

User crosses off:

```text
milk
tomatoes
rice
eggs
spinach
```

System adds bought items to pantry ledger.

### Step 4 — Post-Shopping Silent Check-In

User uploads grocery photos.

System says:

```text
Processing in background. You can keep using the app.
```

Silent enrichment runs.

### Step 5 — Estimate Review

System later shows:

```text
I found 5 estimated items. 2 need review.
```

User confirms/edits values.

### Step 6 — Recipe Request

User asks:

```text
What can I cook tonight?
```

System recommends recipes from ledger.

### Step 7 — Consumption Update

User says:

```text
I used a lot of milk.
```

System asks:

```text
How much milk is left: full, 3/4, 1/2, 1/4, or empty?
```

### Step 8 — Review After First Use

User:

```text
This yogurt was too sour. Don’t recommend this brand again.
```

System stores generalized preference rule.

### Step 9 — Next Shopping List

System avoids that brand and suggests alternatives.

---

## 28. Resume Positioning

### Resume Bullet 1

```text
Built PantryOps Edge, a mobile-first multi-agent grocery memory app that combines checklist-confirmed shopping, edge object detection, OCR/barcode enrichment, editable estimated fields, and LLM-powered meal planning to maintain a structured pantry ledger.
```

### Resume Bullet 2

```text
Designed a fail-safe inventory system using count-based solid quantities, liquid/bulk capacity buckets, source-ranked evidence, field-level confidence metadata, and user-editable estimates to prevent hallucinated inventory updates from vision or LLM outputs.
```

### Resume Bullet 3

```text
Implemented active and silent grocery workflows: active pre-shopping and while-shopping assistance, ad-hoc usage updates, recipe recommendations, and post-shopping background image enrichment through segmentation, OCR, product APIs, and audit agents.
```

---

## 29. Final Principle

PantryOps Edge should never be a magical grocery chatbot.

It should be a reliable grocery operating system.

Final rule:

> **Active help when the user asks. Silent enrichment only after post-shopping check-in. Every estimate is editable. The pantry ledger is the source of truth.**

