# PantryOps Edge — Agent Specification

The 19 agents from `Manifest.md` §15. Each is a class in `backend/app/agents/` with a typed `run(context) -> proposal` method. Agents produce **proposals**; only structured tools commit ledger changes through `services/ledger.py::apply_update()` (invariants 1 and 5 in `architecture.md` §8). The Auditor is the last gate on every user-facing output and every proposal batch.

Orchestration is a custom state machine — no LangGraph at MVP. The Input Router selects agents; each agent's forbidden actions are covered by at least one test.

| # | Agent | File | Enforces invariant |
| - | ----- | ---- | ------------------ |
| 1 | Input Router | `input_router.py` | routing only, no writes |
| 2 | Shopping Planner | `shopping_planner.py` | restriction + preference respect |
| 3 | Checklist Confirmation | `checklist_confirmation.py` | purchase ≠ product details |
| 4 | While-Shopping Assistant | `while_shopping_assistant.py` | no unconfirmed writes |
| 5 | Mobile Check-In | `mobile_check_in.py` | consent (4) |
| 6 | Background Enrichment | `background_enrichment.py` | estimates only (3) |
| 7 | Edge Vision | `edge_vision.py` | category ≠ brand |
| 8 | Segmentation | `segmentation.py` | regions only |
| 9 | OCR / Label | `ocr_label.py` | estimates only |
| 10 | Barcode | `barcode.py` | no invented barcodes |
| 11 | Product Enrichment | `product_enrichment.py` | sourced fields only (2) |
| 12 | Pantry Ledger | `pantry_ledger.py` | single write path (1, 2, 3) |
| 13 | Recipe Planner | `recipe_planner.py` | no auto-deduct (7) |
| 14 | Consumption Update | `consumption_update.py` | ask, don't guess |
| 15 | Preference Review | `preference_review.py` | first-use gate (6) |
| 16 | Store / Cost | `store_cost.py` | no unverified prices |
| 17 | Estimate Review | `estimate_review.py` | surfaces conflicts |
| 18 | Source Attribution | `source_attribution.py` | provenance retention (2) |
| 19 | Auditor | `auditor.py` | everything, last |

---

## 1. Input Router Agent

**Purpose:** Route user inputs to the correct agents.
**Inputs:** user text; image upload; receipt upload; label photo; barcode scan; checklist action; recipe request; ad-hoc update.
**Outputs:** normalized intent; selected agents; structured payload.
**Forbidden:** editing the ledger directly; inferring purchases; generating recipes directly.

## 2. Shopping Planner Agent

**Purpose:** Create shopping lists from pantry state, goals, restrictions, preferences, and upcoming context.
**Inputs:** pantry ledger; user goals; cuisine preferences; protein/carb preference; meat restrictions; budget; product reviews; frequent items; upcoming events.
**Outputs:** categorized shopping list; priority; reason per item; alternatives.
**Forbidden:** marking items as bought; recommending restricted items; ignoring strong negative preference rules.

## 3. Checklist Confirmation Agent

**Purpose:** Confirm bought/not-bought status through user cross-off.
**Inputs:** shopping list item; user action; shopping session.
**Outputs:** purchase confirmation event; pantry insertion proposal (canonical_name confident, everything else `unknown`).
**Forbidden:** inferring exact brand, price, or product size.

## 4. While-Shopping Assistant Agent

**Purpose:** Handle active shopping questions.
**Inputs:** user question; optional image; optional OCR/barcode; current shopping list; pantry ledger; preferences.
**Outputs:** buying advice; product comparison; restriction-aware guidance; optional photo storage/enrichment event.
**Forbidden:** medical claims; claiming exact product identity without evidence; updating the ledger unless the user confirms purchase.

## 5. Mobile Check-In Agent

**Purpose:** Handle post-shopping grocery photo upload and start silent background enrichment.
**Inputs:** uploaded grocery images; shopping session; optional checklist context.
**Outputs:** image records; background job ID; processing status.
**Forbidden:** claiming final identity immediately; auto-confirming low-confidence values; running without user-provided images.

## 6. Background Enrichment Agent

**Purpose:** Run silent product understanding after post-shopping check-in.
**Responsibilities:** call segmentation, detection, OCR, barcode, product enrichment; create estimated records; flag uncertain values.
**Forbidden:** overwriting user-confirmed values; marking estimated fields as confirmed; calling the process "active learning."

## 7. Edge Vision Agent

**Purpose:** Detect grocery objects/categories and estimate counts.
**Inputs:** product/pantry/grocery image; optional expected item list.
**Outputs:** labels; bounding boxes; confidence scores; count estimates.
**Forbidden:** identifying exact brand without OCR/barcode; updating the ledger directly.

## 8. Segmentation Agent

**Purpose:** Segment individual products and create crops for OCR or inspection.
**Inputs:** image; bounding boxes; user-selected region.
**Outputs:** masks; cropped item images; region metadata.
**Forbidden:** classifying the final item alone; writing to the pantry ledger.

## 9. OCR / Label Agent

**Purpose:** Extract text from labels, receipts, packaging, expiry labels, nutrition panels.
**Inputs:** product crop; receipt image; label image.
**Outputs:** raw text; structured key-value candidates; confidence.
**Forbidden:** silently correcting uncertain OCR; marking fields as confirmed.

## 10. Barcode Agent

**Purpose:** Read barcodes when visible and query product sources.
**Inputs:** barcode crop; image; barcode number.
**Outputs:** barcode value; product lookup candidate; confidence.
**Forbidden:** inventing a barcode; matching a product without a reliable barcode value. Returns nothing rather than guessing.

## 11. Product Enrichment Agent

**Purpose:** Use OCR/barcode/product APIs/web sources to enrich product details.
**Inputs:** canonical item; OCR fields; barcode result; image category; product API results; web-search result if enabled.
**Outputs:** brand; product name; package size; dietary info; nutrition fields — all source-labeled.
**Forbidden:** inventing product matches; creating health claims; emitting any unsourced field.

## 12. Pantry Ledger Agent

**Purpose:** Maintain canonical inventory; apply updates by source hierarchy. This is the tool wrapper around `services/ledger.py`.
**Inputs:** checklist confirmations; user edits; OCR estimates; vision estimates; enrichment results; consumption updates; recipe confirmations.
**Outputs:** updated pantry item; change log; source metadata; confidence status.
**Rules:** user confirmation beats model inference; user edit beats all estimates; barcode beats OCR when reliable; OCR beats detection for exact product fields; detection supports category/count; the LLM cannot mutate inventory.

## 13. Recipe Planner Agent

**Purpose:** Recommend meals from available inventory and preferences.
**Inputs:** pantry ledger; cuisine goals; dietary restrictions; protein/carb preference; use-soon items; disliked products/brands.
**Outputs:** recipe suggestions; available ingredients; missing ingredients; expected inventory impact.
**Forbidden:** deducting inventory before user confirmation; recommending restricted foods; claiming unavailable ingredients are available.

## 14. Consumption Update Agent

**Purpose:** Update quantities after use.
**Inputs:** user message; recipe confirmation; quantity state; pantry item.
**Outputs:** quantity update proposal; low-stock flag; reorder trigger.
**Rule:** vague usage ("used a lot of xyz") always triggers a scale question — never a guessed quantity.

## 15. Preference Review Agent

**Purpose:** Store product/brand/category preferences after first use.
**Inputs:** user review; product record; first-use status.
**Outputs:** generalized preference rule; future recommendation adjustment.
**Forbidden:** overgeneralizing brand → category unless the user says so; storing a strong review before first use.

## 16. Store / Cost Agent

**Purpose:** Estimated expense reports and optional store grouping.
**Inputs:** shopping list; store preference; receipt price data; manual prices; product API price if available.
**Outputs:** estimated expense report; known prices; unknown prices; store grouping.
**Forbidden:** claiming live prices or availability without a verified source.

## 17. Estimate Review Agent

**Purpose:** Show uncertain estimated values for confirmation/editing.
**Inputs:** estimated fields; low-confidence records; conflicts; missing values.
**Outputs:** review prompt; user confirmation/edit/rejection. Shows only useful confirmations — no interrupt storms.

## 18. Source Attribution Agent

**Purpose:** Guarantee every field has value, source, confidence, status, editability before it reaches the ledger.
**Inputs:** all candidate fields from other agents.
**Outputs:** source-tracked SourcedField records.
**Forbidden:** merging values without retaining provenance.

## 19. Auditor Agent

**Purpose:** Final gate. Checks outputs and ledger proposals for unsupported claims or unsafe assumptions.
**Audits:** dietary restriction violations; recipes using unavailable items; unsupported product claims; low-confidence estimates displayed as facts; inventory updates without source; preference overgeneralization; silent mode without consent.
**Power:** can block a response or downgrade a proposal to `needs_review`. Runs last, always.
